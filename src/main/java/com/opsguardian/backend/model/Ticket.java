package com.opsguardian.backend.model;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

import lombok.*;

/**
 * Represents a support ticket in the OpsGuardian system.
 * Contains ticket details like title, description, status, and AI-generated suggestions.
 * Maps to the 'tickets' table in the database.
 */

@Entity
@Table(name = "tickets")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@ToString
public class Ticket {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** Brief title/summary of the ticket */
    private String title;

    /** Detailed description of the issue. Limited to 4000 characters. */
    @Column(length = 4000)
    private String description;

    /** User or system that created the ticket */
    private String reporter;
    
    /** Priority level (e.g., HIGH, MEDIUM, LOW) */
    private String priority;
    
    /** Category of the ticket (e.g., NETWORK, SECURITY, PERFORMANCE) */
    private String category;
    
    /** Current status (e.g., OPEN, IN_PROGRESS, RESOLVED, CLOSED) */
    private String status;
    /** When the ticket was created. Defaults to current time if not specified. */
    private Instant createdAt = Instant.now();

    /**
     * List of AI-generated suggestions for resolving this ticket.
     * Stored in a separate 'ticket_suggestions' table with a foreign key relationship.
     */
    @ElementCollection
    @CollectionTable(name = "ticket_suggestions", joinColumns = @JoinColumn(name = "ticket_id"))
    @Column(name = "suggestion", length = 2000)
    private List<String> suggestions = new ArrayList<>();
}
