package com.notes.api.event;

import java.time.Instant;
import java.util.Set;

/**
 * Domain event published when a note is created.
 *
 * <p>A "fat" event: it carries the note's state at creation time, so a consumer
 * (e.g. the classifier) can act on it without calling back to notes-api for the
 * content. Serialized to JSON on the {@code note-events} topic, keyed by the note id.
 */
public record NoteCreated(Long id, String title, String content,
        Set<String> tags, Instant createdAt) {
}
