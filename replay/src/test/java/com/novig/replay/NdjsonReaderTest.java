package com.novig.replay;

import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class NdjsonReaderTest {

    @Test
    void parsesFlatRowWithStringsAndNumbers() {
        Map<String, String> row = NdjsonReader.parseRow(
            "{\"event_id\": \"401859967\", \"home_score\": 90, \"price_american\": -150}");

        assertEquals("401859967", row.get("event_id"));
        assertEquals("90", row.get("home_score"));
        assertEquals("-150", row.get("price_american"));
    }

    @Test
    void parsesEscapedQuotesAndBackslashes() {
        Map<String, String> row = NdjsonReader.parseRow(
            "{\"note\": \"say \\\"hi\\\" \\\\ ok\"}");

        assertEquals("say \"hi\" \\ ok", row.get("note"));
    }

    @Test
    void parsesNullAsNullValue() {
        Map<String, String> row = NdjsonReader.parseRow("{\"winner\": null, \"status\": \"in_progress\"}");

        assertNull(row.get("winner"));
        assertTrue(row.containsKey("winner"));
        assertEquals("in_progress", row.get("status"));
    }

    @Test
    void parsesEmptyObject() {
        Map<String, String> row = NdjsonReader.parseRow("{}");
        assertTrue(row.isEmpty());
    }
}
