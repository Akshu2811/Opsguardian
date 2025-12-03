package com.opsguardian.backend.service;

import com.opsguardian.backend.model.Ticket;
import com.opsguardian.backend.repository.TicketRepository;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

@Service
public class TicketService {
    private final TicketRepository repo;

    public TicketService(TicketRepository repo) {
        this.repo = repo;
    }

    public Ticket create(Ticket t) {
        t.setId(null);
        if (t.getCreatedAt() == null) t.setCreatedAt(Instant.now());
        if (t.getStatus() == null) t.setStatus("OPEN");
        return repo.save(t);
    }

    public Optional<Ticket> get(Long id) {
        return repo.findById(id);
    }

    public List<Ticket> search(String q) {
        if (q == null || q.isBlank()) {
            return repo.findAll();
        }
        return repo.findByTitleContainingIgnoreCaseOrDescriptionContainingIgnoreCase(q, q);
    }

    public Ticket save(Ticket t) {
        return repo.save(t);
    }

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
     * Add suggestions to a ticket by appending them to existing suggestions.
     * Duplicates (exact string matches) are filtered out.
     * Returns the updated ticket, or null if not found.
     */
    public Ticket addSuggestions(Long id, List<String> suggestions) {
        return repo.findById(id)
                .map(t -> {
                    if (t.getSuggestions() == null) {
                        t.setSuggestions(new ArrayList<>());
                    }
                    // append but avoid exact duplicates
                    for (String s : suggestions) {
                        if (s == null) continue;
                        String trimmed = s.trim();
                        if (trimmed.isEmpty()) continue;
                        if (!t.getSuggestions().contains(trimmed)) {
                            t.getSuggestions().add(trimmed);
                        }
                    }

                    // Optionally mark as ASSIGNED if not already
                    if (!"ASSIGNED".equalsIgnoreCase(t.getStatus())) {
                        t.setStatus("ASSIGNED");
                    }
                    return repo.save(t);
                })
                .orElse(null);
    }


}
