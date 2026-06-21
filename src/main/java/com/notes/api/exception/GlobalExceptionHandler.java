package com.notes.api.exception;

import java.util.HashMap;
import java.util.Map;

import org.springframework.http.HttpStatus;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * Central exception handler for every controller in the app.
 *
 * <p>{@code @RestControllerAdvice} is a cross-cutting component: Spring routes
 * exceptions thrown by any controller here, and each method's return value is
 * serialized to JSON just like a normal endpoint. Keeping error translation in
 * one place stops the controllers from filling up with try/catch blocks.</p>
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

	/**
	 * Converts bean-validation failures into a useful response body.
	 *
	 * <p>When a {@code @Valid} request body fails its constraints (e.g. a blank
	 * {@code title}), Spring raises {@link MethodArgumentNotValidException}. By
	 * default that yields a generic "Bad Request" with no detail. Here we flatten
	 * every field error into a {@code {field: message}} map so the client knows
	 * exactly what to fix.</p>
	 *
	 * @param ex the validation failure raised by Spring, carrying every field error
	 * @return a map of field name to its first validation message, sent as HTTP 400
	 */
	@ExceptionHandler(MethodArgumentNotValidException.class)
	@ResponseStatus(HttpStatus.BAD_REQUEST)
	public Map<String, String> handleValidation(MethodArgumentNotValidException ex) {
		Map<String, String> errors = new HashMap<>();
		for (FieldError error : ex.getBindingResult().getFieldErrors()) {
			errors.put(error.getField(), error.getDefaultMessage());
		}
		return errors;
	}
}
