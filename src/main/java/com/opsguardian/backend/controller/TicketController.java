package com.opsguardian.backend.controller;

import com.opsguardian.backend.model.Ticket;
import com.opsguardian.backend.service.TicketService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.*;

@RestController // Marks this as a REST controller exposing JSON APIs
@RequestMapping("/api/tickets") // Base path for all ticket-related endpoints
public class TicketController {

    private final TicketService service; // Ticket service layer for business logic

    public TicketController(TicketService service) {
        this.service = service;
    }

    @GetMapping
    // Returns a list of tickets, with optional search filtering
    public ResponseEntity<List<Ticket>> list(@RequestParam(required = false) String query) {
        List<Ticket> tickets = service.search(query);
        return ResponseEntity.ok(tickets);
    }

    @PostMapping
    // Creates a new ticket with defaults for ID, createdAt, and status
    public ResponseEntity<Ticket> create(@RequestBody Ticket ticket) {
        ticket.setId(null); // Prevent client from injecting ID

        // Set creation timestamp if missing
        if (ticket.getCreatedAt() == null) {
            ticket.setCreatedAt(Instant.now());
        }

        // Default ticket status
        if (ticket.getStatus() == null) {
            ticket.setStatus("OPEN");
        }

        Ticket created = service.create(ticket);
        return ResponseEntity.status(201).body(created);
    }

    @GetMapping("/{id}")
    // Retrieves a specific ticket by ID, or 404 if not found
    public ResponseEntity<Ticket> get(@PathVariable Long id) {
        return service.get(id)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    /**
     * Adds suggestions received from the agent for a given ticket.
     *
     * Supports both JSON array and JSON object payloads.
     * Returns the updated ticket with suggestions included.
     */
    @PostMapping("/{id}/suggestions")
    public ResponseEntity<?> addSuggestions(@PathVariable Long id, @RequestBody Object payload) {
        List<String> suggestions = new ArrayList<>();

        // Handle case where payload is a plain JSON array
        if (payload instanceof List) {
            for (Object o : (List<?>) payload) {
                if (o != null) suggestions.add(String.valueOf(o));
            }
        }
        // Handle case where payload is JSON object
        else if (payload instanceof Map) {
            Map<?, ?> map = (Map<?, ?>) payload;

            Object maybeList = map.get("suggestions");
            // Extract array from "suggestions" key
            if (maybeList instanceof List) {
                for (Object o : (List<?>) maybeList) {
                    if (o != null) suggestions.add(String.valueOf(o));
                }
            } else {
                // Fallback for single suggestion key
                Object single = map.get("suggestion");
                if (single != null) suggestions.add(String.valueOf(single));
            }
        }
        // Fallback: try to coerce any primitive/string payload
        else {
            suggestions.add(String.valueOf(payload));
        }

        // Reject invalid payloads
        if (suggestions.isEmpty()) {
            return ResponseEntity.badRequest()
                    .body(Map.of("status", "error", "reason", "no suggestions found in payload"));
        }

        Ticket updated = service.addSuggestions(id, suggestions);

        // Ticket not found
        if (updated == null) {
            return ResponseEntity.notFound().build();
        }

        return ResponseEntity.ok(Map.of("status", "ok", "ticket", updated));
    }

    @PostMapping("/{id}/apply-suggestion")
    // Placeholder endpoint for applying suggestions—currently logs and returns success
    public ResponseEntity<?> applySuggestion(@PathVariable Long id, @RequestBody Map<String, Object> req) {
        System.out.println("Apply suggestion for ticket " + id + ": " + req);
        return ResponseEntity.ok(Map.of("status", "applied"));
    }

    @PostMapping("/{id}/assign")
    // Assigns a ticket to a specific team and updates its status
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
    // Partially updates a ticket's priority, category, or status fields
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
