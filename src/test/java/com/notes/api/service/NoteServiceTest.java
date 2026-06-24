package com.notes.api.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.Instant;
import java.util.LinkedHashSet;
import java.util.Optional;
import java.util.Set;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.kafka.core.KafkaTemplate;

import com.notes.api.event.NoteCreated;
import com.notes.api.exception.NoteNotFoundException;
import com.notes.api.model.Note;
import com.notes.api.repository.NoteRepository;

/**
 * Unit tests for the service's business rules.
 *
 * <p>No Spring here at all. {@code @Mock} gives us fakes and {@code @InjectMocks}
 * builds a real {@link NoteService} with those fakes passed to its constructor —
 * which is only possible because we used constructor injection. These tests run in
 * milliseconds and assert logic, not wiring.</p>
 */
@ExtendWith(MockitoExtension.class)
class NoteServiceTest {

	@Mock
	private NoteRepository repository;

	@Mock
	private KafkaTemplate<String, Object> kafkaTemplate;

	@InjectMocks
	private NoteService service;

	@Test
	void findById_returnsNote_whenPresent() {
		Note note = new Note("t", "c");
		when(repository.findById(1L)).thenReturn(Optional.of(note));

		assertThat(service.findById(1L)).isSameAs(note);
	}

	@Test
	void findById_throws_whenMissing() {
		when(repository.findById(99L)).thenReturn(Optional.empty());

		assertThatThrownBy(() -> service.findById(99L))
				.isInstanceOf(NoteNotFoundException.class);
	}

	@Test
	void create_savesNote_andPublishesNoteCreatedEvent() {
		Note toSave = new Note("t", "c");
		// id and createdAt are JPA-assigned, so use a mock to control the saved state.
		Note saved = mock(Note.class);
		when(saved.getId()).thenReturn(1L);
		when(saved.getTitle()).thenReturn("t");
		when(saved.getContent()).thenReturn("c");
		when(saved.getTags()).thenReturn(Set.of("java"));
		when(saved.getCreatedAt()).thenReturn(Instant.now());
		when(repository.save(toSave)).thenReturn(saved);

		service.create(toSave);

		verify(repository).save(toSave);
		verify(kafkaTemplate).send(eq("note-events"), eq("1"), any(NoteCreated.class));
	}

	@Test
	void update_copiesFields_andSaves() {
		Note existing = new Note("old title", "old content");
		when(repository.findById(1L)).thenReturn(Optional.of(existing));
		when(repository.save(existing)).thenReturn(existing);

		Note changes = new Note("new title", "new content");
		changes.setTags(new LinkedHashSet<>(Set.of("java")));

		Note result = service.update(1L, changes);

		assertThat(result.getTitle()).isEqualTo("new title");
		assertThat(result.getContent()).isEqualTo("new content");
		assertThat(result.getTags()).containsExactlyInAnyOrder("java");
		verify(repository).save(existing);
	}

	@Test
	void classify_addsNamespacedTags_andPreservesUserTags() {
		Note existing = new Note("t", "c");
		existing.setTags(new LinkedHashSet<>(Set.of("home")));
		when(repository.findById(1L)).thenReturn(Optional.of(existing));
		when(repository.save(existing)).thenReturn(existing);

		Note result = service.classify(1L, "naval", "logistics");

		assertThat(result.getTags())
				.containsExactlyInAnyOrder("home", "category:naval", "domain:logistics");
	}

	@Test
	void classify_isIdempotent_whenAppliedTwice() {
		Note existing = new Note("t", "c");
		when(repository.findById(1L)).thenReturn(Optional.of(existing));
		when(repository.save(existing)).thenReturn(existing);

		// At-least-once redelivery (R1): a second identical apply must not duplicate or accrete.
		service.classify(1L, "naval", "logistics");
		Note result = service.classify(1L, "naval", "logistics");

		assertThat(result.getTags())
				.containsExactlyInAnyOrder("category:naval", "domain:logistics");
	}

	@Test
	void classify_replacesPriorClassification_butKeepsUserTags() {
		Note existing = new Note("t", "c");
		existing.setTags(new LinkedHashSet<>(Set.of("home", "category:industry", "domain:naval")));
		when(repository.findById(1L)).thenReturn(Optional.of(existing));
		when(repository.save(existing)).thenReturn(existing);

		Note result = service.classify(1L, "procurement", "logistics");

		// Upsert: old category:*/domain:* are dropped, the user's "home" survives.
		assertThat(result.getTags())
				.containsExactlyInAnyOrder("home", "category:procurement", "domain:logistics");
	}

	@Test
	void delete_throws_andSkipsDelete_whenMissing() {
		when(repository.existsById(99L)).thenReturn(false);

		assertThatThrownBy(() -> service.delete(99L))
				.isInstanceOf(NoteNotFoundException.class);
		verify(repository, never()).deleteById(99L);
	}

	@Test
	void delete_removes_whenPresent() {
		when(repository.existsById(1L)).thenReturn(true);

		service.delete(1L);

		verify(repository).deleteById(1L);
	}

	@Test
	void search_normalizesBlankArgsToNull() {
		// "  " and "" should be treated as "no filter" before hitting the query.
		service.search("  ", "");

		verify(repository).search(null, null);
	}
}
