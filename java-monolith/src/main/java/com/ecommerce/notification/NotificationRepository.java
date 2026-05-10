package com.ecommerce.notification;

import com.ecommerce.shared.db.DatabaseConnection;
import com.ecommerce.shared.util.Logger;

import java.sql.*;
import java.util.ArrayList;
import java.util.List;

public class NotificationRepository {
    private final Logger logger = new Logger("NotificationRepository");

    public void save(Notification notification) {
        String sql = "INSERT INTO notifications (user_id, type, subject, body, sent_at, delivered) VALUES (?,?,?,?,?,?)";
        try (Connection conn = DatabaseConnection.getInstance().getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setObject(1, notification.getUserId());
            ps.setString(2, notification.getType());
            ps.setString(3, notification.getSubject());
            ps.setString(4, notification.getBody());
            ps.setTimestamp(5, Timestamp.valueOf(notification.getSentAt()));
            ps.setBoolean(6, notification.isDelivered());
            ps.executeUpdate();
        } catch (SQLException e) {
            logger.error("Failed to save notification", e);
        }
    }

    public List<Notification> findByUserId(Long userId) {
        List<Notification> list = new ArrayList<>();
        String sql = "SELECT * FROM notifications WHERE user_id = ? ORDER BY sent_at DESC";
        try (Connection conn = DatabaseConnection.getInstance().getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setLong(1, userId);
            ResultSet rs = ps.executeQuery();
            while (rs.next()) {
                Notification n = new Notification();
                n.setId(rs.getLong("id"));
                n.setDelivered(rs.getBoolean("delivered"));
                list.add(n);
            }
        } catch (SQLException e) {
            logger.error("Failed to find notifications for user: " + userId, e);
        }
        return list;
    }
}
