package com.notes.api.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.util.LinkedHashSet;
import java.util.Optional;
import java.util.Set;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import com.notes.api.exception.NoteNotFoundException;
import com.notes.api.model.Note;
import com.notes.api.repository.NoteRepository;

/**
 * Unit tests for the service's business rules.
 *
 * <p>No Spring here at all. {@code @Mock} gives us a fake repository and
 * {@code @InjectMocks} builds a real {@link NoteService} with that fake passed
 * to its constructor — which is only possible because we used constructor
 * injection. These tests run in milliseconds and assert logic, not wiring.</p>
 */
@ExtendWith(MockitoExtension.class)
class NoteServiceTest {

	@Mock
	private NoteRepository repository;

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
