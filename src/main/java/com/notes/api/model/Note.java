package com.notes.api.model;

import java.time.Instant;
import java.util.LinkedHashSet;
import java.util.Set;

import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import jakarta.persistence.CollectionTable;
import jakarta.persistence.Column;
import jakarta.persistence.ElementCollection;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
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

	// Tags are simple strings owned by this note. @ElementCollection maps a
	// collection of *basic values* (no separate Tag entity) into its own table,
	// here note_tags(note_id, tag). A Set means the same tag can't appear twice
	// on one note. Note: a Set is unordered once Hibernate manages it, so stored
	// order is not the insertion order — use a List + @OrderColumn if you need
	// stable ordering. EAGER loads the tags alongside the note so they're
	// available when we serialize to JSON outside a transaction.
	@ElementCollection(fetch = FetchType.EAGER)
	@CollectionTable(name = "note_tags", joinColumns = @JoinColumn(name = "note_id"))
	@Column(name = "tag", length = 50)
	private Set<String> tags = new LinkedHashSet<>();

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

	public Set<String> getTags() {
		return tags;
	}

	public void setTags(Set<String> tags) {
		// Defensive copy; treat null as "no tags" so the field is never null.
		this.tags = (tags == null) ? new LinkedHashSet<>() : new LinkedHashSet<>(tags);
	}

	public Instant getCreatedAt() {
		return createdAt;
	}

	public Instant getUpdatedAt() {
		return updatedAt;
	}
}
