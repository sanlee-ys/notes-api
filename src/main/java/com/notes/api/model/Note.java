package com.notes.api.model;

import java.time.Instant;

import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/**
 * A single note. @Entity tells JPA/Hibernate this class maps to a database
 * table, so each Note instance becomes one row.
 */
@Entity
@Table(name = "notes")
public class Note {

	// @Id marks the primary key. IDENTITY = let the database auto-increment it,
	// which is the simplest strategy to reason about: the DB hands out the id.
	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	// nullable = false adds a NOT NULL constraint on the column.
	@Column(nullable = false)
	private String title;

	// length raises the default column size (255) so note bodies can be longer.
	@Column(nullable = false, length = 10_000)
	private String content;

	// @CreationTimestamp: Hibernate fills this in automatically on INSERT.
	// updatable = false means it never changes after the row is first written.
	@CreationTimestamp
	@Column(nullable = false, updatable = false)
	private Instant createdAt;

	// @UpdateTimestamp: Hibernate refreshes this on every UPDATE.
	@UpdateTimestamp
	@Column(nullable = false)
	private Instant updatedAt;

	// JPA requires a no-argument constructor to build entities when reading rows.
	protected Note() {
	}

	// Convenience constructor for creating new notes in our own code.
	public Note(String title, String content) {
		this.title = title;
		this.content = content;
	}

	public Long getId() {
		return id;
	}

	public String getTitle() {
		return title;
	}

	public void setTitle(String title) {
		this.title = title;
	}

	public String getContent() {
		return content;
	}

	public void setContent(String content) {
		this.content = content;
	}

	public Instant getCreatedAt() {
		return createdAt;
	}

	public Instant getUpdatedAt() {
		return updatedAt;
	}
}
