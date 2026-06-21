package com.notes.api.exception;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ResponseStatus;

/**
 * Thrown when a note id doesn't exist. Extends RuntimeException (an
 * "unchecked" exception) so callers aren't forced to wrap every call in
 * try/catch.
 *
 * @ResponseStatus tells Spring: whenever this exception escapes a controller,
 * respond with HTTP 404. No try/catch in the controller required.
 */
@ResponseStatus(HttpStatus.NOT_FOUND)
public class NoteNotFoundException extends RuntimeException {

	public NoteNotFoundException(Long id) {
		super("Note not found with id " + id);
	}
}
