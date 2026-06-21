package com.notes.api.repository;

import org.springframework.data.jpa.repository.JpaRepository;

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
 * We only declare extra query methods here when we need them (e.g. search).
 */
public interface NoteRepository extends JpaRepository<Note, Long> {
}
