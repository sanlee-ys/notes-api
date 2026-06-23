package com.notes.api.integration;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Duration;
import java.util.List;
import java.util.Properties;
import java.util.Set;
import java.util.UUID;

import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.consumer.ConsumerRecords;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.kafka.KafkaContainer;
import org.testcontainers.utility.DockerImageName;

import com.notes.api.model.Note;
import com.notes.api.service.NoteService;

/**
 * Integration test: creating a note publishes a real {@code NoteCreated} to Kafka.
 *
 * <p>This is the <strong>producer-side</strong> half of the event-loop round trip
 * (the consumer side lives in the classifier's
 * {@code tests/test_consumer_integration.py}). Where {@code NoteServiceTest} fakes
 * the {@code KafkaTemplate} with a Mockito mock, this boots the real app against a
 * real Kafka broker running in Docker and asserts an actual message lands on the
 * {@code note-events} topic with the wire shape {@code system/SYS-005} froze.</p>
 *
 * <h2>Reading this if you know Testcontainers from Python</h2>
 * The concepts are identical to {@code testcontainers[kafka]} in pytest; only the
 * machinery differs. The mapping:
 * <ul>
 *   <li>{@code @Testcontainers} + {@code @Container} on a static field
 *       ≈ a module-scoped pytest fixture that starts the container once and stops it
 *       at the end. JUnit manages the lifecycle from the annotations instead of a
 *       {@code yield} fixture.</li>
 *   <li>{@code disabledWithoutDocker = true}
 *       ≈ the Python fixture's {@code pytest.skip(...)} when Docker isn't reachable —
 *       the test is skipped, not failed, on a machine without Docker.</li>
 *   <li>{@code @ServiceConnection}
 *       ≈ reading {@code container.get_bootstrap_server()} and passing it to your
 *       client — except Spring Boot does it for you, auto-wiring the broker's address
 *       into {@code spring.kafka.*} so the app's {@code KafkaTemplate} publishes to
 *       this container. (No {@code @DynamicPropertySource} needed.)</li>
 *   <li>This file being named {@code *IT} (not {@code *Test}) + the Failsafe plugin
 *       ≈ the {@code @pytest.mark.integration} + {@code --run-integration} opt-in:
 *       {@code ./mvnw test} skips it, {@code ./mvnw verify} runs it (needs Docker).</li>
 *   <li>The raw {@link KafkaConsumer} below ≈ the kafka-python {@code KafkaConsumer}
 *       in the Python IT: a throwaway consumer that reads the topic to verify what was
 *       published.</li>
 * </ul>
 *
 * <p><strong>Note:</strong> this was written without a local JRE, so CI
 * ({@code ./mvnw -B verify}, which has Docker) is its first real run. The most likely
 * thing to need a one-line tweak is the {@link KafkaContainer} image/class for the
 * exact Testcontainers version the Boot 4.1 BOM resolves.</p>
 */
@SpringBootTest
@Testcontainers(disabledWithoutDocker = true)
class NoteEventPublishingIT {

	/**
	 * A throwaway Kafka broker, started once for this class and torn down after.
	 * {@code @ServiceConnection} points the app's Kafka producer at it automatically.
	 */
	@Container
	@ServiceConnection
	static KafkaContainer kafka =
			new KafkaContainer(DockerImageName.parse("apache/kafka:3.8.0"));

	@Autowired
	private NoteService service;

	@Test
	void creatingANote_publishesNoteCreatedToKafka() {
		// Create a note through the real service — which saves it and publishes the
		// event via the real KafkaTemplate (wired to the container). The HTTP layer
		// that fronts this is covered by NoteControllerTest, so driving the service
		// directly keeps the IT focused on the publish behaviour.
		Note toSave = new Note(
				"Navy awards UAV contract",
				"The Navy awarded a maintenance contract for carrier-based drones.");
		toSave.setTags(Set.of("mine"));
		Note saved = service.create(toSave);
		String key = String.valueOf(saved.getId());

		ConsumerRecord<String, String> record = readOne("note-events", key);

		// Key is the note id (so per-note events stay ordered).
		assertThat(record.key()).isEqualTo(key);
		// Value is the "fat event" as plain JSON — exactly the SYS-005 wire shape the
		// Python consumer deserializes.
		assertThat(record.value())
				.contains("\"id\":" + saved.getId())
				.contains("\"title\":\"Navy awards UAV contract\"")
				.contains("\"mine\"");
		// No Java type headers — the consumer is the (Python) classifier, so the
		// producer is configured with spring.json.add.type.headers=false.
		assertThat(record.headers().lastHeader("__TypeId__")).isNull();
	}

	/**
	 * Reads the first record with {@code wantKey} off {@code topic}, polling up to a
	 * deadline. A fresh consumer group + {@code auto.offset.reset=earliest} means it
	 * sees the message even though it was published before this consumer existed.
	 */
	private ConsumerRecord<String, String> readOne(String topic, String wantKey) {
		Properties props = new Properties();
		props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, kafka.getBootstrapServers());
		props.put(ConsumerConfig.GROUP_ID_CONFIG, "it-" + UUID.randomUUID());
		props.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
		props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
		props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);

		try (KafkaConsumer<String, String> consumer = new KafkaConsumer<>(props)) {
			consumer.subscribe(List.of(topic));
			long deadline = System.currentTimeMillis() + 20_000;
			while (System.currentTimeMillis() < deadline) {
				ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(500));
				for (ConsumerRecord<String, String> record : records) {
					if (wantKey.equals(record.key())) {
						return record;
					}
				}
			}
		}
		throw new AssertionError(
				"no NoteCreated with key " + wantKey + " on topic " + topic);
	}
}
