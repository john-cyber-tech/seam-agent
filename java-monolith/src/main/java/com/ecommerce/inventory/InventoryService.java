package com.ecommerce.inventory;

import com.ecommerce.shared.db.DatabaseConnection;
import com.ecommerce.shared.util.Logger;

import java.sql.*;
import java.util.Optional;

public class InventoryService {
    private final Logger logger = new Logger("InventoryService");

    public boolean isAvailable(Long productId, int quantity) {
        String sql = "SELECT stock_quantity FROM inventory WHERE product_id = ?";
        try (Connection conn = DatabaseConnection.getInstance().getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setLong(1, productId);
            ResultSet rs = ps.executeQuery();
            if (rs.next()) return rs.getInt("stock_quantity") >= quantity;
        } catch (SQLException e) {
            logger.error("Failed to check availability for product: " + productId, e);
        }
        return false;
    }

    public void reserve(Long productId, int quantity) {
        String sql = "UPDATE inventory SET stock_quantity = stock_quantity - ?, reserved_quantity = reserved_quantity + ? WHERE product_id = ?";
        try (Connection conn = DatabaseConnection.getInstance().getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setInt(1, quantity);
            ps.setInt(2, quantity);
            ps.setLong(3, productId);
            ps.executeUpdate();
            logger.info("Reserved " + quantity + " units of product: " + productId);
        } catch (SQLException e) {
            logger.error("Failed to reserve inventory for product: " + productId, e);
        }
    }

    public void release(Long productId, int quantity) {
        String sql = "UPDATE inventory SET stock_quantity = stock_quantity + ?, reserved_quantity = reserved_quantity - ? WHERE product_id = ?";
        try (Connection conn = DatabaseConnection.getInstance().getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setInt(1, quantity);
            ps.setInt(2, quantity);
            ps.setLong(3, productId);
            ps.executeUpdate();
            logger.info("Released " + quantity + " units of product: " + productId);
        } catch (SQLException e) {
            logger.error("Failed to release inventory for product: " + productId, e);
        }
    }

    public Optional<Product> getProduct(Long productId) {
        String sql = "SELECT p.*, i.stock_quantity FROM products p JOIN inventory i ON p.id = i.product_id WHERE p.id = ?";
        try (Connection conn = DatabaseConnection.getInstance().getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setLong(1, productId);
            ResultSet rs = ps.executeQuery();
            if (rs.next()) {
                return Optional.of(new Product(
                    rs.getLong("id"),
                    rs.getString("name"),
                    rs.getDouble("price"),
                    rs.getInt("stock_quantity")
                ));
            }
        } catch (SQLException e) {
            logger.error("Failed to get product: " + productId, e);
        }
        return Optional.empty();
    }

    public void restock(Long productId, int quantity) {
        String sql = "UPDATE inventory SET stock_quantity = stock_quantity + ? WHERE product_id = ?";
        try (Connection conn = DatabaseConnection.getInstance().getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setInt(1, quantity);
            ps.setLong(2, productId);
            ps.executeUpdate();
            logger.info("Restocked " + quantity + " units of product: " + productId);
        } catch (SQLException e) {
            logger.error("Failed to restock product: " + productId, e);
        }
    }
}
