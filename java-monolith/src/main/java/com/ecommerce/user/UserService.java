package com.ecommerce.user;

import com.ecommerce.notification.NotificationService;
import com.ecommerce.shared.model.User;
import com.ecommerce.shared.util.DateUtils;
import com.ecommerce.shared.util.Logger;

import java.util.List;
import java.util.Optional;

public class UserService {
    private final UserRepository userRepository = new UserRepository();
    private final NotificationService notificationService = new NotificationService();
    private final Logger logger = new Logger("UserService");

    public Optional<User> getUserById(Long id) {
        return userRepository.findById(id);
    }

    public Optional<User> getUserByEmail(String email) {
        return userRepository.findByEmail(email);
    }

    public List<User> getAllUsers() {
        return userRepository.findAll();
    }

    public User register(String username, String email, String passwordHash) {
        User user = new User(null, username, email, "CUSTOMER");
        user.setPasswordHash(passwordHash);
        user.setCreatedAt(DateUtils.now());
        userRepository.save(user);
        notificationService.sendWelcomeEmail(user);
        logger.info("Registered new user: " + email);
        return user;
    }

    public void deactivate(Long userId) {
        userRepository.findById(userId).ifPresent(user -> {
            user.setActive(false);
            userRepository.update(user);
            notificationService.sendAccountDeactivationEmail(user);
            logger.info("Deactivated user: " + userId);
        });
    }

    public boolean emailExists(String email) {
        return userRepository.findByEmail(email).isPresent();
    }
}
