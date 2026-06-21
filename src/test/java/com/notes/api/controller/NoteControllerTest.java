package com.notes.api.controller;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

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
}
