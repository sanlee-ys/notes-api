package com.notes.api.repository;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Arrays;
import java.util.LinkedHashSet;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;

import com.notes.api.model.Note;

/**
 * Tests the custom {@code search} query against a real (in-memory) database.
 *
 * <p>{@code @DataJpaTest} boots just the JPA slice — entities, repositories, and
 * an embedded H2 — not the web layer. Each test runs in its own transaction that
 * rolls back afterward, so the tests don't pollute each other. This is where the
 * actual JPQL gets exercised; a Mockito fake couldn't catch a query bug.</p>
 */
@DataJpaTest
class NoteRepositoryTest {

	@Autowired
	private NoteRepository repository;

	private static Note note(String title, String content, String... tags) {
		Note n = new Note(title, content);
		n.setTags(new LinkedHashSet<>(Arrays.asList(tags)));
		return n;
	}

	@BeforeEach
	void seed() {
		repository.save(note("Buy milk", "2% and oat", "groceries", "home"));
		repository.save(note("Spring notes", "constructor injection", "java", "spring"));
		repository.save(note("JPA tips", "element collections and queries", "java", "jpa"));
	}

	@Test
	void search_withNoFilters_returnsAll() {
		assertThat(repository.search(null, null)).hasSize(3);
	}

	@Test
	void search_byText_isCaseInsensitive_andMatchesTitleOrContent() {
		assertThat(repository.search("MILK", null))
				.extracting(Note::getTitle).containsExactly("Buy milk");
		assertThat(repository.search("injection", null))
				.extracting(Note::getTitle).containsExactly("Spring notes");
	}

	@Test
	void search_byTag_returnsEveryNoteWithThatTag() {
		assertThat(repository.search(null, "java"))
				.extracting(Note::getTitle)
				.containsExactlyInAnyOrder("Spring notes", "JPA tips");
	}

	@Test
	void search_byTextAndTag_combinesWithAnd() {
		assertThat(repository.search("collections", "jpa"))
				.extracting(Note::getTitle).containsExactly("JPA tips");
		// "milk" matches only the groceries note, which has no "java" tag -> empty.
		assertThat(repository.search("milk", "java")).isEmpty();
	}
}
