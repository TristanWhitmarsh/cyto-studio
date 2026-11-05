import math


def safe_contrast_limits(value_range, brightness=1):
    """Return finite, strictly increasing display limits without changing data."""
    lower, upper = map(float, value_range)
    scaled_upper = upper * float(brightness)
    if not math.isfinite(lower):
        lower = 0.0
    if math.isfinite(scaled_upper) and scaled_upper > lower:
        return [lower, scaled_upper]
    # Keep the original data range if brightness collapsed or inverted it.
    if math.isfinite(upper) and upper > lower:
        return [lower, upper]
    upper = lower + max(1.0, abs(lower) * 0.01)
    if not math.isfinite(upper):
        return [0.0, 1.0]
    return [lower, upper]


def parse_channel_input(input_string):
    channels = []
    # Remove spaces and split input by commas
    input_string = input_string.replace(" ", "")
    parts = input_string.split(',')

    for part in parts:
        if '-' in part:
            # Handle ranges
            start, end = part.split('-')
            try:
                start = int(start)-1
                end = int(end)-1
                channels.extend(range(start, end + 1))
            except ValueError:
                print(f"Invalid range: {part}")
        else:
            # Single channel
            try:
                channels.append(int(part)-1)
            except ValueError:
                print(f"Invalid channel: {part}")

    return channels
