package com.ecommerce.order;

import com.ecommerce.shared.db.DatabaseConnection;
import com.ecommerce.shared.util.Logger;

import java.sql.*;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

public class OrderRepository {
    private final Logger logger = new Logger("OrderRepository");

    public Optional<Order> findById(Long id) {
        String sql = "SELECT * FROM orders WHERE id = ?";
        try (Connection conn = DatabaseConnection.getInstance().getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setLong(1, id);
            ResultSet rs = ps.executeQuery();
            if (rs.next()) {
                Order order = mapRow(rs);
                order.getItems().addAll(findItemsByOrderId(id));
                return Optional.of(order);
            }
        } catch (SQLException e) {
            logger.error("Failed to find order: " + id, e);
        }
        return Optional.empty();
    }

    public List<Order> findByUserId(Long userId) {
        List<Order> orders = new ArrayList<>();
        String sql = "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC";
        try (Connection conn = DatabaseConnection.getInstance().getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setLong(1, userId);
            ResultSet rs = ps.executeQuery();
            while (rs.next()) {
                Order order = mapRow(rs);
                order.getItems().addAll(findItemsByOrderId(order.getId()));
                orders.add(order);
            }
        } catch (SQLException e) {
            logger.error("Failed to find orders for user: " + userId, e);
        }
        return orders;
    }

    public List<Order> findByStatus(String status) {
        List<Order> orders = new ArrayList<>();
        String sql = "SELECT * FROM orders WHERE status = ?";
        try (Connection conn = DatabaseConnection.getInstance().getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setString(1, status);
            ResultSet rs = ps.executeQuery();
            while (rs.next()) orders.add(mapRow(rs));
        } catch (SQLException e) {
            logger.error("Failed to find orders by status: " + status, e);
        }
        return orders;
    }

    public void save(Order order) {
        String sql = "INSERT INTO orders (user_id, status, total_amount, shipping_address, created_at) VALUES (?,?,?,?,?)";
        try (Connection conn = DatabaseConnection.getInstance().getConnection();
             PreparedStatement ps = conn.prepareStatement(sql, Statement.RETURN_GENERATED_KEYS)) {
            ps.setLong(1, order.getUserId());
            ps.setString(2, order.getStatus());
            ps.setDouble(3, order.getTotalAmount());
            ps.setString(4, order.getShippingAddress());
            ps.setTimestamp(5, Timestamp.valueOf(order.getCreatedAt()));
            ps.executeUpdate();
            ResultSet keys = ps.getGeneratedKeys();
            if (keys.next()) {
                order.setId(keys.getLong(1));
                saveItems(order);
            }
        } catch (SQLException e) {
            logger.error("Failed to save order", e);
        }
    }

    public void updateStatus(Long orderId, String status) {
        String sql = "UPDATE orders SET status = ?, updated_at = NOW() WHERE id = ?";
        try (Connection conn = DatabaseConnection.getInstance().getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setString(1, status);
            ps.setLong(2, orderId);
            ps.executeUpdate();
        } catch (SQLException e) {
            logger.error("Failed to update order status: " + orderId, e);
        }
    }

    private void saveItems(Order order) throws SQLException {
        String sql = "INSERT INTO order_items (order_id, product_id, product_name, quantity, unit_price) VALUES (?,?,?,?,?)";
        try (Connection conn = DatabaseConnection.getInstance().getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            for (OrderItem item : order.getItems()) {
                ps.setLong(1, order.getId());
                ps.setLong(2, item.getProductId());
                ps.setString(3, item.getProductName());
                ps.setInt(4, item.getQuantity());
                ps.setDouble(5, item.getUnitPrice());
                ps.addBatch();
            }
            ps.executeBatch();
        }
    }

    private List<OrderItem> findItemsByOrderId(Long orderId) {
        List<OrderItem> items = new ArrayList<>();
        String sql = "SELECT * FROM order_items WHERE order_id = ?";
        try (Connection conn = DatabaseConnection.getInstance().getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setLong(1, orderId);
            ResultSet rs = ps.executeQuery();
            while (rs.next()) {
                OrderItem item = new OrderItem();
                item.setId(rs.getLong("id"));
                item.setOrderId(rs.getLong("order_id"));
                items.add(item);
            }
        } catch (SQLException e) {
            logger.error("Failed to find items for order: " + orderId, e);
        }
        return items;
    }

    private Order mapRow(ResultSet rs) throws SQLException {
        Order o = new Order();
        o.setId(rs.getLong("id"));
        o.setCreatedAt(rs.getTimestamp("created_at").toLocalDateTime());
        o.setStatus(rs.getString("status"));
        o.setTotalAmount(rs.getDouble("total_amount"));
        return o;
    }
}
