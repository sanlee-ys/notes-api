package com.notes.api.dto;

import java.time.Instant;
import java.util.Set;

import com.notes.api.model.Note;

/**
 * What the API sends back. Decoupling this from the Note entity means we can
 * change the database shape without changing the API contract (and vice
 * versa), and we never accidentally expose internal-only fields.
 */
public record NoteResponse(
		Long id,
		String title,
		String content,
		Set<String> tags,
		Instant createdAt,
		Instant updatedAt
) {

	// Static factory: entity -> response DTO. Keeping the mapping here means
	// the controller stays thin and there's one place to update if either
	// shape changes.
	public static NoteResponse from(Note note) {
		return new NoteResponse(
				note.getId(),
				note.getTitle(),
				note.getContent(),
				note.getTags(),
				note.getCreatedAt(),
				note.getUpdatedAt());
	}
}
