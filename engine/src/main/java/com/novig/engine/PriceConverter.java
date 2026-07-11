package com.novig.engine;

/**
 * Converts American odds to price ticks in [0, {@link SettlementEngine#MAX_PRICE_TICKS}],
 * the implied probability (in cents) that the quoted side wins.
 */
public final class PriceConverter {

    private PriceConverter() {}

    public static long americanOddsToPriceTicks(int americanOdds) {
        if (americanOdds == 0) {
            throw new IllegalArgumentException("American odds cannot be 0");
        }

        double impliedProbability = americanOdds > 0
            ? 100.0 / (americanOdds + 100.0)
            : (double) -americanOdds / (-americanOdds + 100.0);

        return (long) (impliedProbability * SettlementEngine.MAX_PRICE_TICKS);
    }
}
