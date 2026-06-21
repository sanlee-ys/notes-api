package com.notes.api.repository;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import com.notes.api.model.Note;

/**
 * Data-access layer for notes.
 *
 * Notice there is no implementation here — just an interface. At startup,
 * Spring Data JPA generates a concrete class behind this interface and
 * registers it as a bean. By extending JpaRepository<Note, Long> (entity
 * type = Note, primary-key type = Long) we inherit ready-made methods:
 *
 *   save(note)        insert or update
 *   findById(id)      look up one note (returns Optional<Note>)
 *   findAll()         every note
 *   deleteById(id)    delete one
 *   count(), existsById(id), ...
 *
 * For anything beyond those, we declare the method ourselves — either by
 * naming convention (Spring derives the query from the method name) or, as
 * below, with an explicit @Query.
 */
public interface NoteRepository extends JpaRepository<Note, Long> {

	/**
	 * Searches notes by free text and/or a tag. Both filters are optional: a
	 * {@code null} argument means "don't filter on this", so the four
	 * combinations (neither / q only / tag only / both) all flow through one query.
	 *
	 * <p>This is <b>JPQL</b> (Jakarta Persistence Query Language) — it queries over
	 * entities and fields ({@code Note}, {@code n.title}), not database tables and
	 * columns, so it stays portable across databases. The {@code """ """} text
	 * block is a Java 15+ feature for multi-line strings. {@code LEFT JOIN n.tags t}
	 * lets us match against the element-collection tags, and {@code DISTINCT}
	 * collapses the duplicate rows that join produces.</p>
	 *
	 * @param q   case-insensitive substring to match in title or content (nullable)
	 * @param tag case-insensitive exact tag to require (nullable)
	 * @return matching notes
	 */
	@Query("""
			SELECT DISTINCT n FROM Note n LEFT JOIN n.tags t
			WHERE (:q IS NULL
			       OR LOWER(n.title) LIKE LOWER(CONCAT('%', :q, '%'))
			       OR LOWER(n.content) LIKE LOWER(CONCAT('%', :q, '%')))
			  AND (:tag IS NULL OR LOWER(t) = LOWER(:tag))
			""")
	List<Note> search(@Param("q") String q, @Param("tag") String tag);
}
