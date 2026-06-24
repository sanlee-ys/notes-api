package com.notes.api.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * What the classifier sends to set a note's classification.
 *
 * <p>Deliberately tiny and separate from {@link NoteRequest}: this is a <em>partial</em>
 * update (PATCH) that carries only the classification, never title or content — the classifier
 * has no business setting those (see {@code decisions/ADR-002}). Both fields are required
 * because v0 always writes a category and a domain together.</p>
 *
 * <p>The {@code @Size(max = 40)} leaves room for the namespace prefix: each value is stored as
 * {@code "category:" + value} (or {@code "domain:" + value}), and a note tag column holds at
 * most 50 characters, so 40 keeps the namespaced tag within bounds (9-char {@code "category:"}
 * + 40 = 49).</p>
 */
public record ClassificationRequest(

		@NotBlank(message = "category must not be blank")
		@Size(max = 40, message = "category must be at most 40 characters")
		String category,

		@NotBlank(message = "operationalDomain must not be blank")
		@Size(max = 40, message = "operationalDomain must be at most 40 characters")
		String operationalDomain
) {
}
