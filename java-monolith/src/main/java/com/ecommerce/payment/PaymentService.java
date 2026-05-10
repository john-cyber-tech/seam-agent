package com.ecommerce.payment;

import com.ecommerce.shared.db.DatabaseConnection;
import com.ecommerce.shared.util.DateUtils;
import com.ecommerce.shared.util.Logger;

import java.sql.*;
import java.util.Optional;

public class PaymentService {
    private final Logger logger = new Logger("PaymentService");

    public boolean processPayment(Long orderId, double amount, String paymentToken) {
        logger.info("Processing payment for order: " + orderId + ", amount: " + amount);
        boolean success = chargeExternalGateway(paymentToken, amount);
        saveTransaction(orderId, amount, success ? "SUCCESS" : "FAILED", paymentToken);
        return success;
    }

    public boolean refund(Long orderId, double amount) {
        logger.info("Refunding order: " + orderId + ", amount: " + amount);
        boolean success = refundExternalGateway(orderId, amount);
        saveTransaction(orderId, amount, success ? "REFUNDED" : "REFUND_FAILED", null);
        return success;
    }

    public Optional<PaymentRecord> getPaymentRecord(Long orderId) {
        String sql = "SELECT * FROM payments WHERE order_id = ?";
        try (Connection conn = DatabaseConnection.getInstance().getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setLong(1, orderId);
            ResultSet rs = ps.executeQuery();
            if (rs.next()) {
                return Optional.of(new PaymentRecord(
                    rs.getLong("id"),
                    rs.getLong("order_id"),
                    rs.getDouble("amount"),
                    rs.getString("status"),
                    rs.getTimestamp("created_at").toLocalDateTime()
                ));
            }
        } catch (SQLException e) {
            logger.error("Failed to get payment record for order: " + orderId, e);
        }
        return Optional.empty();
    }

    public double getTotalRevenue() {
        String sql = "SELECT SUM(amount) FROM payments WHERE status = 'SUCCESS'";
        try (Connection conn = DatabaseConnection.getInstance().getConnection();
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(sql)) {
            if (rs.next()) return rs.getDouble(1);
        } catch (SQLException e) {
            logger.error("Failed to calculate total revenue", e);
        }
        return 0.0;
    }

    private void saveTransaction(Long orderId, double amount, String status, String token) {
        String sql = "INSERT INTO payments (order_id, amount, status, payment_token, created_at) VALUES (?,?,?,?,?)";
        try (Connection conn = DatabaseConnection.getInstance().getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setLong(1, orderId);
            ps.setDouble(2, amount);
            ps.setString(3, status);
            ps.setString(4, token);
            ps.setTimestamp(5, Timestamp.valueOf(DateUtils.now()));
            ps.executeUpdate();
        } catch (SQLException e) {
            logger.error("Failed to save transaction for order: " + orderId, e);
        }
    }

    private boolean chargeExternalGateway(String token, double amount) {
        return !token.isEmpty() && amount > 0;
    }

    private boolean refundExternalGateway(Long orderId, double amount) {
        return amount > 0;
    }
}
