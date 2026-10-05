def reset_usage():
    # Start a fresh count for a new question; earlier results keep their own dict
    global usage
    usage = {"input_tokens": 0, "output_tokens": 0,
             "generation": {"input_tokens": 0, "output_tokens": 0},
             "judge": {"input_tokens": 0, "output_tokens": 0}}
    return usage


# Tokens spent on the current question: the total over every API call, and split by call kind
reset_usage()


def record_usage(response, kind):
    # kind: "generation" or "judge"
    for counts in [usage, usage[kind]]:
        counts["input_tokens"] += response.usage.input_tokens
        counts["output_tokens"] += response.usage.output_tokens


def usage_cost(counts, config):
    return (counts["input_tokens"] * config["input_price"]
            + counts["output_tokens"] * config["output_price"]) / 1_000_000
