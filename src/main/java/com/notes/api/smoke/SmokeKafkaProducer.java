package com.notes.api.smoke;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Profile;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

import java.time.Instant;

/**
 * Phase 0 smoke test: proves notes-api can talk to Kafka.
 *
 * <p>
 * Publishes one message to the {@code smoke-test} topic on startup, but ONLY
 * under the
 * {@code smoke} Spring profile — so it never fires during the test suite (which
 * has no broker)
 * or during a normal boot. Run it with {@code SPRING_PROFILES_ACTIVE=smoke}.
 *
 * <p>
 * Throwaway: delete this once real {@code NoteCreated} events replace it.
 */
@Component
@Profile("smoke")
public class SmokeKafkaProducer implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(SmokeKafkaProducer.class);
    private static final String TOPIC = "smoke-test";

    private final KafkaTemplate<String, String> kafkaTemplate;

    public SmokeKafkaProducer(KafkaTemplate<String, String> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    @Override
    public void run(ApplicationArguments args) {
        String message = "notes-api speaks Kafka — rust officially shaken off 🎸" + Instant.now();
        kafkaTemplate.send(TOPIC, "note-1", message)
                .whenComplete((result, ex) -> {
                    if (ex == null) {
                        var md = result.getRecordMetadata();
                        log.info("[smoke] published to {}-{} @ offset {}: {}",
                                md.topic(), md.partition(), md.offset(), message);
                    } else {
                        log.error("[smoke] failed to publish to {}: {}", TOPIC, ex.getMessage(), ex);
                    }
                });
    }
}
