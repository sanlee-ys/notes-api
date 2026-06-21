package com.notes.api.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * What a client is allowed to send when creating or updating a note.
 *
 * This is a `record` — a compact, immutable data carrier. The compiler
 * generates the constructor, accessors (title(), content()), equals/hashCode,
 * and toString for you. Closest Python analogy: a frozen @dataclass.
 *
 * Crucially, there is NO id / createdAt / updatedAt here. Those are
 * server-controlled, so the client simply has no field to set them with.
 * Validation annotations on the components run when the controller marks the
 * argument @Valid.
 */
public record NoteRequest(

		@NotBlank(message = "title must not be blank")
		@Size(max = 255, message = "title must be at most 255 characters")
		String title,

		@NotBlank(message = "content must not be blank")
		@Size(max = 10_000, message = "content must be at most 10000 characters")
		String content
) {
}
