package com.notes.api.controller;

import static org.hamcrest.Matchers.containsInAnyOrder;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.LinkedHashSet;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import com.notes.api.exception.NoteNotFoundException;
import com.notes.api.model.Note;
import com.notes.api.service.NoteService;

/**
 * Tests the web layer in isolation.
 *
 * <p>{@code @WebMvcTest} loads only the controller, the JSON machinery, and the
 * {@code @RestControllerAdvice} — no database, no real service. The service is
 * replaced by a Mockito mock via {@code @MockitoBean}, so these tests assert HTTP
 * concerns only: status codes, JSON shape, validation, and that the controller
 * delegates correctly. {@link MockMvc} fires fake requests without a real server.</p>
 */
@WebMvcTest(NoteController.class)
class NoteControllerTest {

	@Autowired
	private MockMvc mockMvc;

	@MockitoBean
	private NoteService service;

	@Test
	void create_returns201_andBody() throws Exception {
		when(service.create(any(Note.class))).thenReturn(new Note("Buy milk", "2% and oat"));

		mockMvc.perform(post("/notes")
						.contentType(MediaType.APPLICATION_JSON)
						.content("""
								{"title":"Buy milk","content":"2% and oat","tags":["home"]}"""))
				.andExpect(status().isCreated())
				.andExpect(jsonPath("$.title").value("Buy milk"))
				.andExpect(jsonPath("$.content").value("2% and oat"));
	}

	@Test
	void create_withBlankTitle_returns400_andSkipsService() throws Exception {
		mockMvc.perform(post("/notes")
						.contentType(MediaType.APPLICATION_JSON)
						.content("""
								{"title":"","content":"x"}"""))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.title").exists());

		// Validation rejects the request before the controller calls the service.
		verifyNoInteractions(service);
	}

	@Test
	void getOne_whenMissing_returns404() throws Exception {
		when(service.findById(99L)).thenThrow(new NoteNotFoundException(99L));

		mockMvc.perform(get("/notes/99"))
				.andExpect(status().isNotFound());
	}

	@Test
	void getAll_passesQueryParamsToService() throws Exception {
		when(service.search("milk", "home")).thenReturn(List.of());

		mockMvc.perform(get("/notes").param("q", "milk").param("tag", "home"))
				.andExpect(status().isOk());

		verify(service).search("milk", "home");
	}

	@Test
	void getAll_returnsJsonArrayOfNotes_withContractFields() throws Exception {
		// Pins the GET /notes read contract (system/SYS-006) on the provider side:
		// the 200 body is a JSON ARRAY whose elements carry id/title/content/tags —
		// the exact shape kb-agent's search_notes tool consumes.
		Note note = new Note("Drone doctrine", "UAV ROE");
		note.setTags(new LinkedHashSet<>(List.of("domain:air")));
		when(service.search(null, null)).thenReturn(List.of(note));

		mockMvc.perform(get("/notes"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$").isArray())
				.andExpect(jsonPath("$[0].title").value("Drone doctrine"))
				.andExpect(jsonPath("$[0].content").value("UAV ROE"))
				.andExpect(jsonPath("$[0].tags").isArray())
				.andExpect(jsonPath("$[0].tags[0]").value("domain:air"));
	}

	@Test
	void getOne_returns200_andBody() throws Exception {
		when(service.findById(1L)).thenReturn(new Note("Buy milk", "2% and oat"));

		mockMvc.perform(get("/notes/1"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.title").value("Buy milk"))
				.andExpect(jsonPath("$.content").value("2% and oat"));
	}

	@Test
	void update_returns200_andBody() throws Exception {
		when(service.update(eq(1L), any(Note.class)))
				.thenReturn(new Note("New title", "New content"));

		mockMvc.perform(put("/notes/1")
						.contentType(MediaType.APPLICATION_JSON)
						.content("""
								{"title":"New title","content":"New content"}"""))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.title").value("New title"))
				.andExpect(jsonPath("$.content").value("New content"));
	}

	@Test
	void updateTags_returns200_andReplacedTags() throws Exception {
		Note retagged = new Note("Buy milk", "2% and oat");
		retagged.setTags(new LinkedHashSet<>(List.of("category:procurement", "domain:land")));
		when(service.setTags(eq(1L), any())).thenReturn(retagged);

		mockMvc.perform(put("/notes/1/tags")
						.contentType(MediaType.APPLICATION_JSON)
						.content("""
								{"tags":["category:procurement","domain:land"]}"""))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.tags").isArray())
				.andExpect(jsonPath("$.tags", containsInAnyOrder("category:procurement", "domain:land")));

		verify(service).setTags(eq(1L), any());
	}

	@Test
	void updateTags_whenMissing_returns404() throws Exception {
		when(service.setTags(eq(99L), any())).thenThrow(new NoteNotFoundException(99L));

		mockMvc.perform(put("/notes/99/tags")
						.contentType(MediaType.APPLICATION_JSON)
						.content("""
								{"tags":["category:operations"]}"""))
				.andExpect(status().isNotFound());
	}

	@Test
	void delete_returns204_andDelegatesToService() throws Exception {
		mockMvc.perform(delete("/notes/1"))
				.andExpect(status().isNoContent());

		verify(service).delete(1L);
	}
}
