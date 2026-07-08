package com.novig.engine;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class PriceConverterTest {

    @Test
    void negativeFavoriteConvertsToImpliedProbability() {
        assertEquals(60, PriceConverter.americanOddsToPriceTicks(-150));
        assertEquals(75, PriceConverter.americanOddsToPriceTicks(-300));
        assertEquals(80, PriceConverter.americanOddsToPriceTicks(-400));
    }

    @Test
    void positiveUnderdogConvertsToImpliedProbability() {
        assertEquals(50, PriceConverter.americanOddsToPriceTicks(100));
        assertEquals(40, PriceConverter.americanOddsToPriceTicks(150));
        assertEquals(25, PriceConverter.americanOddsToPriceTicks(300));
    }

    @Test
    void rejectsZeroOdds() {
        assertThrows(IllegalArgumentException.class, () -> PriceConverter.americanOddsToPriceTicks(0));
    }
}
