package com.notes.api.dto;

import java.util.Set;

import jakarta.validation.constraints.Size;

/**
 * What a client sends to set a note's tags wholesale.
 *
 * <p>Used by {@code PUT /notes/{id}/tags} — the idempotent tag-writeback seam the
 * defense-news-classifier's consumer calls after classifying a {@code NoteCreated}
 * event. It carries <em>only</em> tags (no title/content), so a consumer can retag
 * a note without resending — and risking clobbering — the note body. Same per-note
 * and per-tag limits as {@link NoteRequest}, so the two tag inputs validate alike.</p>
 */
public record TagsRequest(

		// Same two constraints as NoteRequest.tags: @Size on the field caps how many
		// tags a note may have; @Size on the type argument caps each tag's length.
		@Size(max = 20, message = "a note can have at most 20 tags")
		Set<@Size(max = 50, message = "each tag must be at most 50 characters") String> tags
) {
}
