package com.ecommerce.user;

import com.ecommerce.shared.model.User;
import com.ecommerce.shared.util.DateUtils;
import com.ecommerce.shared.util.Logger;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

public class AuthService {
    private final UserRepository userRepository = new UserRepository();
    private final Logger logger = new Logger("AuthService");
    private final Map<String, Long> activeSessions = new HashMap<>();

    public Optional<String> login(String email, String passwordHash) {
        Optional<User> userOpt = userRepository.findByEmail(email);
        if (userOpt.isPresent()) {
            User user = userOpt.get();
            if (user.isActive() && user.getPasswordHash().equals(passwordHash)) {
                String token = UUID.randomUUID().toString();
                activeSessions.put(token, user.getId());
                logger.info("User logged in: " + email);
                return Optional.of(token);
            }
        }
        logger.warn("Failed login attempt for: " + email);
        return Optional.empty();
    }

    public void logout(String token) {
        activeSessions.remove(token);
        logger.info("Session invalidated: " + token);
    }

    public Optional<User> validateToken(String token) {
        Long userId = activeSessions.get(token);
        if (userId != null) {
            return userRepository.findById(userId);
        }
        return Optional.empty();
    }

    public boolean hasRole(String token, String role) {
        return validateToken(token)
            .map(u -> u.getRole().equals(role))
            .orElse(false);
    }
}
