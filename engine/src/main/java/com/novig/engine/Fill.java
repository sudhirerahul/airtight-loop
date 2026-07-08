package com.novig.engine;

import java.time.Instant;

public record Fill(
    String marketId,
    String restingOrderId,
    Order.Side restingSide,
    String incomingOrderId,
    Order.Side incomingSide,
    long priceTicks,
    int quantity,
    Instant timestamp
) {}
