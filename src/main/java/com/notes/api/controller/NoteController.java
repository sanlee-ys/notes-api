package com.notes.api.controller;

import java.util.List;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.notes.api.dto.NoteRequest;
import com.notes.api.dto.NoteResponse;
import com.notes.api.model.Note;
import com.notes.api.service.NoteService;

import jakarta.validation.Valid;

/**
 * REST endpoints for notes, served under {@code /notes}.
 *
 * <p>The controller speaks DTOs at its edges — {@link NoteRequest} in,
 * {@link NoteResponse} out — and the {@link Note} entity never leaves this
 * layer. That keeps the public API contract independent of the database shape.
 * {@code @RestController} means each method's return value is serialized
 * straight to the response body as JSON (via Jackson).</p>
 */
@RestController
@RequestMapping("/notes")
public class NoteController {

	private final NoteService service;

	public NoteController(NoteService service) {
		this.service = service;
	}

	/**
	 * Lists all notes.
	 *
	 * <p>{@code stream().map(NoteResponse::from).toList()} is Java's pipeline
	 * equivalent of a Python list comprehension: take each entity, convert it to a
	 * response DTO, collect into a list. {@code NoteResponse::from} is a method
	 * reference — shorthand for the lambda {@code n -> NoteResponse.from(n)}.</p>
	 *
	 * @return every note as a list of response DTOs (HTTP 200)
	 */
	@GetMapping
	public List<NoteResponse> getAll() {
		return service.findAll().stream()
				.map(NoteResponse::from)
				.toList();
	}

	/**
	 * Fetches a single note.
	 *
	 * @param id the note id, bound from the URL path via {@code @PathVariable}
	 * @return the note as a response DTO (HTTP 200); HTTP 404 if it does not exist
	 */
	@GetMapping("/{id}")
	public NoteResponse getOne(@PathVariable Long id) {
		return NoteResponse.from(service.findById(id));
	}

	/**
	 * Creates a new note.
	 *
	 * <p>{@code @Valid} runs the {@code @NotBlank}/{@code @Size} checks on the
	 * request body before this method executes; a violation short-circuits to
	 * HTTP 400. Because {@link NoteRequest} has no id or timestamp fields, a
	 * client cannot set those server-controlled values.</p>
	 *
	 * @param request the validated create payload (title + content)
	 * @return the created note as a response DTO (HTTP 201)
	 */
	@PostMapping
	@ResponseStatus(HttpStatus.CREATED)
	public NoteResponse create(@Valid @RequestBody NoteRequest request) {
		Note saved = service.create(new Note(request.title(), request.content()));
		return NoteResponse.from(saved);
	}

	/**
	 * Replaces the title and content of an existing note.
	 *
	 * @param id      the id of the note to update
	 * @param request the validated payload with the new title + content
	 * @return the updated note as a response DTO (HTTP 200); HTTP 404 if it does not exist
	 */
	@PutMapping("/{id}")
	public NoteResponse update(@PathVariable Long id, @Valid @RequestBody NoteRequest request) {
		Note updated = service.update(id, new Note(request.title(), request.content()));
		return NoteResponse.from(updated);
	}

	/**
	 * Deletes a note.
	 *
	 * @param id the id of the note to delete
	 * @return nothing; HTTP 204 on success, HTTP 404 if it does not exist
	 */
	@DeleteMapping("/{id}")
	@ResponseStatus(HttpStatus.NO_CONTENT)
	public void delete(@PathVariable Long id) {
		service.delete(id);
	}
}
