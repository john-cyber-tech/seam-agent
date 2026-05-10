package com.ecommerce.reporting;

import com.ecommerce.inventory.InventoryService;
import com.ecommerce.payment.PaymentService;
import com.ecommerce.shared.db.DatabaseConnection;
import com.ecommerce.shared.util.DateUtils;
import com.ecommerce.shared.util.Logger;
import com.ecommerce.user.UserService;

import java.sql.*;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class ReportingService {
    private final PaymentService paymentService = new PaymentService();
    private final UserService userService = new UserService();
    private final InventoryService inventoryService = new InventoryService();
    private final Logger logger = new Logger("ReportingService");

    public SalesReport generateSalesReport(LocalDateTime from, LocalDateTime to) {
        logger.info("Generating sales report from " + DateUtils.format(from) + " to " + DateUtils.format(to));

        double totalRevenue = paymentService.getTotalRevenue();
        int totalOrders = countOrders(from, to);
        int totalUsers = userService.getAllUsers().size();
        List<Map<String, Object>> topProducts = getTopSellingProducts(from, to);

        return new SalesReport(totalRevenue, totalOrders, totalUsers, topProducts, from, to);
    }

    public Map<String, Double> getRevenueByMonth() {
        Map<String, Double> result = new HashMap<>();
        String sql = "SELECT DATE_FORMAT(created_at, '%Y-%m') as month, SUM(amount) as revenue " +
                     "FROM payments WHERE status = 'SUCCESS' GROUP BY month ORDER BY month";
        try (Connection conn = DatabaseConnection.getInstance().getConnection();
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(sql)) {
            while (rs.next()) {
                result.put(rs.getString("month"), rs.getDouble("revenue"));
            }
        } catch (SQLException e) {
            logger.error("Failed to get revenue by month", e);
        }
        return result;
    }

    public List<Map<String, Object>> getLowStockProducts(int threshold) {
        List<Map<String, Object>> products = new ArrayList<>();
        String sql = "SELECT p.id, p.name, i.stock_quantity FROM products p " +
                     "JOIN inventory i ON p.id = i.product_id WHERE i.stock_quantity < ?";
        try (Connection conn = DatabaseConnection.getInstance().getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setInt(1, threshold);
            ResultSet rs = ps.executeQuery();
            while (rs.next()) {
                Map<String, Object> row = new HashMap<>();
                row.put("id", rs.getLong("id"));
                row.put("name", rs.getString("name"));
                row.put("stock", rs.getInt("stock_quantity"));
                products.add(row);
            }
        } catch (SQLException e) {
            logger.error("Failed to get low stock products", e);
        }
        return products;
    }

    public Map<String, Integer> getOrderStatusBreakdown() {
        Map<String, Integer> result = new HashMap<>();
        String sql = "SELECT status, COUNT(*) as count FROM orders GROUP BY status";
        try (Connection conn = DatabaseConnection.getInstance().getConnection();
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(sql)) {
            while (rs.next()) {
                result.put(rs.getString("status"), rs.getInt("count"));
            }
        } catch (SQLException e) {
            logger.error("Failed to get order status breakdown", e);
        }
        return result;
    }

    private int countOrders(LocalDateTime from, LocalDateTime to) {
        String sql = "SELECT COUNT(*) FROM orders WHERE created_at BETWEEN ? AND ?";
        try (Connection conn = DatabaseConnection.getInstance().getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setTimestamp(1, Timestamp.valueOf(from));
            ps.setTimestamp(2, Timestamp.valueOf(to));
            ResultSet rs = ps.executeQuery();
            if (rs.next()) return rs.getInt(1);
        } catch (SQLException e) {
            logger.error("Failed to count orders", e);
        }
        return 0;
    }

    private List<Map<String, Object>> getTopSellingProducts(LocalDateTime from, LocalDateTime to) {
        List<Map<String, Object>> products = new ArrayList<>();
        String sql = "SELECT oi.product_id, oi.product_name, SUM(oi.quantity) as total_sold " +
                     "FROM order_items oi JOIN orders o ON oi.order_id = o.id " +
                     "WHERE o.created_at BETWEEN ? AND ? AND o.status = 'CONFIRMED' " +
                     "GROUP BY oi.product_id, oi.product_name ORDER BY total_sold DESC LIMIT 10";
        try (Connection conn = DatabaseConnection.getInstance().getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setTimestamp(1, Timestamp.valueOf(from));
            ps.setTimestamp(2, Timestamp.valueOf(to));
            ResultSet rs = ps.executeQuery();
            while (rs.next()) {
                Map<String, Object> row = new HashMap<>();
                row.put("productId", rs.getLong("product_id"));
                row.put("name", rs.getString("product_name"));
                row.put("totalSold", rs.getInt("total_sold"));
                products.add(row);
            }
        } catch (SQLException e) {
            logger.error("Failed to get top selling products", e);
        }
        return products;
    }
}
