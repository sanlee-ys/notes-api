package com.notes.api.service;

import java.util.List;
import java.util.Set;

import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.notes.api.event.NoteCreated;
import com.notes.api.exception.NoteNotFoundException;
import com.notes.api.model.Note;
import com.notes.api.repository.NoteRepository;

/**
 * Business logic for notes.
 *
 * <p>Sits between the controller (web layer) and the repository (data layer).
 * It owns the rules — e.g. "fetch must 404 when missing" and "update is a
 * read-modify-write" — so those rules live in one place regardless of who
 * calls them. {@code @Service} registers it as a Spring-managed bean so it can
 * be injected into the controller.</p>
 */
@Service
public class NoteService {

	/** Topic carrying note lifecycle events, keyed by note id so per-note order holds. */
	private static final String NOTE_EVENTS_TOPIC = "note-events";

	private final NoteRepository repository;
	private final KafkaTemplate<String, Object> kafkaTemplate;

	/**
	 * Spring injects the repository and Kafka template via constructor injection — it
	 * sees the single constructor and supplies the matching beans automatically.
	 *
	 * <p>Preferred over field {@code @Autowired}: the fields can be {@code final}
	 * (set once, never reassigned) and the class is trivial to unit-test with a plain
	 * {@code new NoteService(mockRepo, mockTemplate)} — no Spring container required.</p>
	 *
	 * @param repository    the data-access bean for notes
	 * @param kafkaTemplate publishes domain events to Kafka
	 */
	public NoteService(NoteRepository repository, KafkaTemplate<String, Object> kafkaTemplate) {
		this.repository = repository;
		this.kafkaTemplate = kafkaTemplate;
	}

	/**
	 * Returns every note.
	 *
	 * @return all stored notes (an empty list if there are none)
	 */
	public List<Note> findAll() {
		return repository.findAll();
	}

	/**
	 * Searches notes by optional free text and/or tag.
	 *
	 * <p>Blank or whitespace-only parameters are normalized to {@code null} so an
	 * empty query string (e.g. {@code ?q=}) behaves the same as omitting it. With
	 * both filters absent this returns every note.</p>
	 *
	 * @param q   substring to match in title/content, or null/blank for no text filter
	 * @param tag exact tag to require, or null/blank for no tag filter
	 * @return matching notes
	 */
	public List<Note> search(String q, String tag) {
		return repository.search(blankToNull(q), blankToNull(tag));
	}

	private static String blankToNull(String value) {
		return (value == null || value.isBlank()) ? null : value.trim();
	}

	/**
	 * Looks up a single note by id.
	 *
	 * <p>{@code findById} returns {@code Optional<Note>} — Java's "maybe a value"
	 * wrapper — and {@code orElseThrow} forces the missing case to be handled
	 * explicitly instead of letting a {@code null} slip downstream (roughly the
	 * difference between {@code dict[key]} and {@code dict.get(key)} in Python).</p>
	 *
	 * @param id the note's primary key
	 * @return the matching note
	 * @throws NoteNotFoundException if no note has that id
	 */
	public Note findById(Long id) {
		return repository.findById(id)
				.orElseThrow(() -> new NoteNotFoundException(id));
	}

	/**
	 * Saves a brand-new note and publishes a {@link NoteCreated} event.
	 *
	 * <p>The id and timestamps are assigned by the database and Hibernate on
	 * insert, so any such values on the incoming object are irrelevant.</p>
	 *
	 * <p>The event is published <em>after</em> the save returns, i.e. after the row
	 * is committed. The DB write and the Kafka send are <strong>not</strong> atomic —
	 * a crash between them could drop the event. That dual-write limitation is
	 * accepted for now and recorded in the event-driven ADR; the transactional outbox
	 * pattern is the production-grade fix.</p>
	 *
	 * @param note a not-yet-persisted note carrying the title and content
	 * @return the saved note, now populated with a generated id and timestamps
	 */
	public Note create(Note note) {
		Note saved = repository.save(note);
		NoteCreated event = new NoteCreated(saved.getId(), saved.getTitle(),
				saved.getContent(), saved.getTags(), saved.getCreatedAt());
		kafkaTemplate.send(NOTE_EVENTS_TOPIC, saved.getId().toString(), event);
		return saved;
	}

	/**
	 * Updates the title, content, and tags of an existing note.
	 *
	 * <p>Read-modify-write: the existing row is loaded, its fields are overwritten,
	 * and it is saved — all inside one transaction ({@code @Transactional}), so the
	 * steps either all succeed or all roll back. {@code createdAt} is preserved;
	 * {@code updatedAt} is refreshed automatically by Hibernate.</p>
	 *
	 * @param id      the id of the note to update
	 * @param changes a note carrying the new title and content
	 * @return the updated, persisted note
	 * @throws NoteNotFoundException if no note has that id
	 */
	@Transactional
	public Note update(Long id, Note changes) {
		Note existing = findById(id);
		existing.setTitle(changes.getTitle());
		existing.setContent(changes.getContent());
		existing.setTags(changes.getTags());
		return repository.save(existing);
	}

	/**
	 * Replaces just the tags of an existing note; title and content are untouched.
	 *
	 * <p>Read-modify-write in one transaction, mirroring {@link #update} but scoped to
	 * tags. Replace semantics make it <strong>idempotent</strong>: applying the same
	 * tag set repeatedly — as an at-least-once consumer redelivering a
	 * {@code NoteCreated} event will — leaves the note in the same final state. That
	 * is the writeback half of the event loop (notes-api {@code ADR-001} risk R1,
	 * {@code system/SYS-005}).</p>
	 *
	 * @param id   the id of the note to retag
	 * @param tags the new tag set (already cleaned and de-duplicated by the caller)
	 * @return the updated, persisted note
	 * @throws NoteNotFoundException if no note has that id
	 */
	@Transactional
	public Note setTags(Long id, Set<String> tags) {
		Note existing = findById(id);
		existing.setTags(tags);
		return repository.save(existing);
	}

	/**
	 * Deletes a note by id.
	 *
	 * <p>Checks existence first so deleting a non-existent note produces a clean
	 * 404 rather than failing silently.</p>
	 *
	 * @param id the id of the note to delete
	 * @throws NoteNotFoundException if no note has that id
	 */
	public void delete(Long id) {
		if (!repository.existsById(id)) {
			throw new NoteNotFoundException(id);
		}
		repository.deleteById(id);
	}
}
