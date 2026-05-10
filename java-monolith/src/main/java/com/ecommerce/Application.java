package com.ecommerce;

import com.ecommerce.order.OrderService;
import com.ecommerce.reporting.ReportingService;
import com.ecommerce.shared.util.DateUtils;
import com.ecommerce.shared.util.Logger;
import com.ecommerce.user.AuthService;
import com.ecommerce.user.UserService;

public class Application {
    private static final Logger logger = new Logger("Application");

    public static void main(String[] args) {
        logger.info("Starting ECommerce Monolith at " + DateUtils.format(DateUtils.now()));

        UserService userService = new UserService();
        AuthService authService = new AuthService();
        OrderService orderService = new OrderService();
        ReportingService reportingService = new ReportingService();

        logger.info("All services initialized. Application ready.");
    }
}
