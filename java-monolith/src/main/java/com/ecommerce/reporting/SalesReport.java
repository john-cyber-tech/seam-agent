package com.ecommerce.reporting;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

public class SalesReport {
    private final double totalRevenue;
    private final int totalOrders;
    private final int totalUsers;
    private final List<Map<String, Object>> topProducts;
    private final LocalDateTime from;
    private final LocalDateTime to;

    public SalesReport(double totalRevenue, int totalOrders, int totalUsers,
                       List<Map<String, Object>> topProducts, LocalDateTime from, LocalDateTime to) {
        this.totalRevenue = totalRevenue;
        this.totalOrders = totalOrders;
        this.totalUsers = totalUsers;
        this.topProducts = topProducts;
        this.from = from;
        this.to = to;
    }

    public double getTotalRevenue() { return totalRevenue; }
    public int getTotalOrders() { return totalOrders; }
    public int getTotalUsers() { return totalUsers; }
    public List<Map<String, Object>> getTopProducts() { return topProducts; }
    public LocalDateTime getFrom() { return from; }
    public LocalDateTime getTo() { return to; }

    @Override
    public String toString() {
        return String.format("SalesReport[from=%s, to=%s, revenue=%.2f, orders=%d, users=%d]",
            from, to, totalRevenue, totalOrders, totalUsers);
    }
}
