-- src/main/resources/data.sql
-- Insert initial sample tickets. Do NOT set ID here; let the DB auto-generate it.

INSERT INTO tickets (title, description, reporter, priority, category, status, created_at) VALUES
                                                                                               ('Database connection failed', 'Application reports DB connection timeout when fetching orders', 'alice@example.com', 'P0', 'Database', 'OPEN', CURRENT_TIMESTAMP),
                                                                                               ('Login page error', 'Users receive 500 when trying to login', 'bob@example.com', 'P1', 'Application', 'OPEN', CURRENT_TIMESTAMP),
                                                                                               ('Password reset not working', 'Password reset emails not delivered', 'charlie@example.com', 'P2', 'Access', 'OPEN', CURRENT_TIMESTAMP),
                                                                                               ('Intermittent high latency', 'Service latency spikes on checkout', 'dan@example.com', 'P1', 'Application', 'OPEN', CURRENT_TIMESTAMP),
                                                                                               ('New user provisioning fails', 'Onboarding script fails for several users', 'ema@example.com', 'P2', 'Access', 'OPEN', CURRENT_TIMESTAMP),
                                                                                               ('Disk space low on DB node', 'DB node disk usage 95% alerts', 'frank@example.com', 'P0', 'Database', 'OPEN', CURRENT_TIMESTAMP),
                                                                                               ('Payment gateway timeout', 'Payments failing intermittently', 'grace@example.com', 'P1', 'Network', 'OPEN', CURRENT_TIMESTAMP),
                                                                                               ('Service health check failing', 'Health check returns 503 sporadically', 'henry@example.com', 'P1', 'Application', 'OPEN', CURRENT_TIMESTAMP),
                                                                                               ('Duplicate order creation', 'Orders duplicated after retry', 'irene@example.com', 'P2', 'Application', 'OPEN', CURRENT_TIMESTAMP),
                                                                                               ('VPN access blocked', 'Remote worker cannot access internal resources', 'jack@example.com', 'P1', 'Network', 'OPEN', CURRENT_TIMESTAMP);
