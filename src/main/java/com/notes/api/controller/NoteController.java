package com.notes.api.controller;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.notes.api.dto.ClassificationRequest;
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
	 * Lists notes, optionally filtered by free text and/or a tag.
	 *
	 * <p>Both query params are optional ({@code required = false}). With neither,
	 * this returns every note. {@code stream().map(NoteResponse::from).toList()} is
	 * Java's pipeline equivalent of a Python list comprehension: take each entity,
	 * convert it to a response DTO, collect into a list. {@code NoteResponse::from}
	 * is a method reference — shorthand for {@code n -> NoteResponse.from(n)}.</p>
	 *
	 * @param q   optional substring to match in title/content (e.g. {@code ?q=milk})
	 * @param tag optional exact tag to require (e.g. {@code ?tag=java})
	 * @return matching notes as response DTOs (HTTP 200)
	 */
	@GetMapping
	public List<NoteResponse> getAll(
			@RequestParam(required = false) String q,
			@RequestParam(required = false) String tag) {
		return service.search(q, tag).stream()
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
	 * @param request the validated create payload (title + content + optional tags)
	 * @return the created note as a response DTO (HTTP 201)
	 */
	@PostMapping
	@ResponseStatus(HttpStatus.CREATED)
	public NoteResponse create(@Valid @RequestBody NoteRequest request) {
		return NoteResponse.from(service.create(toEntity(request)));
	}

	/**
	 * Replaces the title, content, and tags of an existing note.
	 *
	 * @param id      the id of the note to update
	 * @param request the validated payload with the new title, content, and tags
	 * @return the updated note as a response DTO (HTTP 200); HTTP 404 if it does not exist
	 */
	@PutMapping("/{id}")
	public NoteResponse update(@PathVariable Long id, @Valid @RequestBody NoteRequest request) {
		return NoteResponse.from(service.update(id, toEntity(request)));
	}

	/**
	 * Sets a note's classification (category + operational domain).
	 *
	 * <p>A <em>partial</em> update used by the classifier service. Unlike {@code PUT}, it touches
	 * only the classification — never title or content — and it is idempotent: applying the same
	 * classification twice is a no-op (see {@code decisions/ADR-002}). The labels are stored as
	 * namespaced tags ({@code category:*}, {@code domain:*}).</p>
	 *
	 * @param id      the id of the note to classify
	 * @param request the validated classification payload (category + operationalDomain)
	 * @return the updated note as a response DTO (HTTP 200); HTTP 404 if it does not exist
	 */
	@PatchMapping("/{id}/classification")
	public NoteResponse classify(@PathVariable Long id, @Valid @RequestBody ClassificationRequest request) {
		return NoteResponse.from(service.classify(id, request.category(), request.operationalDomain()));
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

	/**
	 * Builds a Note entity from a validated request, cleaning the tags on the way.
	 *
	 * @param request the incoming request DTO
	 * @return a transient Note carrying the request's title, content, and cleaned tags
	 */
	private static Note toEntity(NoteRequest request) {
		Note note = new Note(request.title(), request.content());
		note.setTags(cleanTags(request.tags()));
		return note;
	}

	/**
	 * Normalizes incoming tags: drops nulls/blanks and trims whitespace. The
	 * resulting {@link Set} also removes exact duplicates. (Case is preserved as
	 * the client sent it — lowercasing would be a separate design choice.)
	 *
	 * @param raw the tags from the request (may be null)
	 * @return a clean, de-duplicated, order-preserving set of tags
	 */
	private static Set<String> cleanTags(Set<String> raw) {
		if (raw == null) {
			return new LinkedHashSet<>();
		}
		return raw.stream()
				.filter(tag -> tag != null)
				.map(String::trim)
				.filter(tag -> !tag.isEmpty())
				.collect(Collectors.toCollection(LinkedHashSet::new));
	}
}
