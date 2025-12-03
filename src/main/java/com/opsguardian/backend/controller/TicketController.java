package com.opsguardian.backend.controller;

import com.opsguardian.backend.model.Ticket;
import com.opsguardian.backend.service.TicketService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.*;

@RestController
@RequestMapping("/api/tickets")
public class TicketController {

    private final TicketService service;

    public TicketController(TicketService service) {
        this.service = service;
    }

    @GetMapping
    public ResponseEntity<List<Ticket>> list(@RequestParam(required = false) String query) {
        List<Ticket> tickets = service.search(query);
        return ResponseEntity.ok(tickets);
    }

    @PostMapping
    public ResponseEntity<Ticket> create(@RequestBody Ticket ticket) {
        // Defensive: ensure we never try to persist a Ticket with an explicit id
        ticket.setId(null);

        // Ensure createdAt and status defaults for new tickets
        if (ticket.getCreatedAt() == null) {
            ticket.setCreatedAt(Instant.now());
        }
        if (ticket.getStatus() == null) {
            ticket.setStatus("OPEN");
        }

        Ticket created = service.create(ticket);
        return ResponseEntity.status(201).body(created);
    }

    @GetMapping("/{id}")
    public ResponseEntity<Ticket> get(@PathVariable Long id) {
        return service.get(id)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    /**
     * Accepts suggestions from the agent and persists them to the ticket.
     *
     * Accepts either:
     *  - a JSON array: ["s1", "s2"]
     *  - or an object: {"suggestions": ["s1","s2"], ...}
     *
     * Returns the updated Ticket in the response.
     */
    @PostMapping("/{id}/suggestions")
    public ResponseEntity<?> addSuggestions(@PathVariable Long id, @RequestBody Object payload) {
        List<String> suggestions = new ArrayList<>();

        // payload can be ArrayList (when JSON array is posted) or LinkedHashMap (when object posted)
        if (payload instanceof List) {
            for (Object o : (List<?>) payload) {
                if (o != null) suggestions.add(String.valueOf(o));
            }
        } else if (payload instanceof Map) {
            Map<?, ?> map = (Map<?, ?>) payload;
            Object maybeList = map.get("suggestions");
            if (maybeList instanceof List) {
                for (Object o : (List<?>) maybeList) {
                    if (o != null) suggestions.add(String.valueOf(o));
                }
            } else {
                // fallback: if map contains string values under different keys,
                // try to collect them (defensive)
                Object single = map.get("suggestion");
                if (single != null) suggestions.add(String.valueOf(single));
            }
        } else {
            // last-resort: string payload mapping — try to coerce
            suggestions.add(String.valueOf(payload));
        }

        if (suggestions.isEmpty()) {
            return ResponseEntity.badRequest().body(Map.of("status", "error", "reason", "no suggestions found in payload"));
        }

        Ticket updated = service.addSuggestions(id, suggestions);
        if (updated == null) {
            return ResponseEntity.notFound().build();
        }

        return ResponseEntity.ok(Map.of("status", "ok", "ticket", updated));
    }

    // placeholder: apply a suggestion (simulate)
    @PostMapping("/{id}/apply-suggestion")
    public ResponseEntity<?> applySuggestion(@PathVariable Long id, @RequestBody Map<String, Object> req) {
        System.out.println("Apply suggestion for ticket " + id + ": " + req);
        return ResponseEntity.ok(Map.of("status", "applied"));
    }

    // assign ticket to team
    @PostMapping("/{id}/assign")
    public ResponseEntity<?> assign(@PathVariable Long id, @RequestBody Map<String, Object> assignment) {
        service.get(id).ifPresent(t -> {
            Object team = assignment.get("team");
            t.setStatus("ASSIGNED");
            service.save(t);
            System.out.println("Assigned ticket " + id + " to " + team);
        });
        return ResponseEntity.ok(Map.of("status", "assigned"));
    }

    @PutMapping("/{id}")
    public ResponseEntity<Ticket> update(
            @PathVariable Long id,
            @RequestBody Map<String, Object> changes
    ) {
        String priority = (String) changes.get("priority");
        String category = (String) changes.get("category");
        String status   = (String) changes.get("status");

        Ticket updated = service.updateFields(id, priority, category, status);

        if (updated == null) {
            return ResponseEntity.notFound().build();
        }

        return ResponseEntity.ok(updated);
    }
}
