response_format = (
    {
        "type": "json_schema",
        "json_schema": {
            "name": "movie_recommendation",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "address": {"type": "string"},
                    "movies": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "rating": {"type": "string"},
                                "showtimes": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": ["title", "rating", "showtimes"],
                        },
                    },
                    "reason": {"type": "string"},
                },
                "required": ["name", "address", "movies", "reason"],
            },
        },
    },
)
