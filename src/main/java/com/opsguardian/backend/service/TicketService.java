package com.opsguardian.backend.service;

import com.opsguardian.backend.model.Ticket;
import com.opsguardian.backend.repository.TicketRepository;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

@Service // Service layer: encapsulates business logic and repository interactions
public class TicketService {
    private final TicketRepository repo; // Repository for persistence operations

    public TicketService(TicketRepository repo) {
        this.repo = repo;
    }

    // Create a new ticket with defensive defaults (no client-supplied ID,
    // ensure createdAt and status are set) and persist it.
    public Ticket create(Ticket t) {
        t.setId(null);
        if (t.getCreatedAt() == null) t.setCreatedAt(Instant.now());
        if (t.getStatus() == null) t.setStatus("OPEN");
        return repo.save(t);
    }

    // Retrieve a ticket by ID; returns Optional to represent presence/absence.
    public Optional<Ticket> get(Long id) {
        return repo.findById(id);
    }

    // Search tickets by query string. If query is blank, return all tickets.
    // Uses repository's case-insensitive "contains" finder for title/description.
    public List<Ticket> search(String q) {
        if (q == null || q.isBlank()) {
            return repo.findAll();
        }
        return repo.findByTitleContainingIgnoreCaseOrDescriptionContainingIgnoreCase(q, q);
    }

    // Save an existing ticket (simple pass-through to repository).
    public Ticket save(Ticket t) {
        return repo.save(t);
    }

    // Partially update a ticket's selected fields (priority, category, status).
    // If the ticket is not found, return null to let the caller handle 404.
    public Ticket updateFields(Long id, String priority, String category, String status) {
        return repo.findById(id)
                .map(t -> {
                    if (priority != null) t.setPriority(priority);
                    if (category != null) t.setCategory(category);
                    if (status != null) t.setStatus(status);
                    return repo.save(t);
                })
                .orElse(null);
    }

    /**
     * Append new suggestions to an existing ticket.
     *
     * Behavior:
     *  - Initializes suggestions list if missing.
     *  - Trims input, ignores null/empty entries.
     *  - Avoids adding exact duplicate suggestion strings.
     *  - Marks ticket as ASSIGNED if it isn't already (business decision).
     *  - Returns the updated ticket, or null if ticket not found.
     */
    public Ticket addSuggestions(Long id, List<String> suggestions) {
        return repo.findById(id)
                .map(t -> {
                    if (t.getSuggestions() == null) {
                        t.setSuggestions(new ArrayList<>());
                    }
                    // Append suggestions while filtering null/empty and duplicates
                    for (String s : suggestions) {
                        if (s == null) continue;
                        String trimmed = s.trim();
                        if (trimmed.isEmpty()) continue;
                        if (!t.getSuggestions().contains(trimmed)) {
                            t.getSuggestions().add(trimmed);
                        }
                    }

                    // Business rule: move to ASSIGNED when suggestions are added
                    if (!"ASSIGNED".equalsIgnoreCase(t.getStatus())) {
                        t.setStatus("ASSIGNED");
                    }
                    return repo.save(t);
                })
                .orElse(null);
    }

}
