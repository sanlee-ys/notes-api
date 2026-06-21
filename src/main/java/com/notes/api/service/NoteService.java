package com.notes.api.service;

import java.util.List;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

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

	private final NoteRepository repository;

	/**
	 * Spring injects the repository here via constructor injection — it sees the
	 * single constructor and supplies the {@link NoteRepository} bean automatically.
	 *
	 * <p>Preferred over field {@code @Autowired}: the field can be {@code final}
	 * (set once, never reassigned) and the class is trivial to unit-test with a
	 * plain {@code new NoteService(mockRepo)} — no Spring container required.</p>
	 *
	 * @param repository the data-access bean for notes
	 */
	public NoteService(NoteRepository repository) {
		this.repository = repository;
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
	 * Saves a brand-new note.
	 *
	 * <p>The id and timestamps are assigned by the database and Hibernate on
	 * insert, so any such values on the incoming object are irrelevant.</p>
	 *
	 * @param note a not-yet-persisted note carrying the title and content
	 * @return the saved note, now populated with a generated id and timestamps
	 */
	public Note create(Note note) {
		return repository.save(note);
	}

	/**
	 * Updates the title and content of an existing note.
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
