/**
 * pipe_parse.h - Shared pipe-delimited options/arguments parser for the C launcher
 *
 * Parses values sourced from assets/options_arguments.set that populate menus
 * (dynamically generated GUI components), define priority for arrays that fill
 * comboboxes, and define preset values with fallbacks delimited by "|".
 *
 * The parser is self-contained and requires NO additional dependencies beyond
 * the standard C library (string.h, stddef.h, stdlib.h).
 *
 * Empty-token handling is critical:
 *   " |tokenA|tokenB|tokenC| "  has an empty-token priority (leading '|').
 *   The launcher observes the absent (empty) elements when building
 *   launcher-parameters; i.e. an empty option/argument is omitted from the
 *   resulting command string.
 */

#ifndef PIPE_PARSE_H
#define PIPE_PARSE_H

#include <string.h>
#include <stddef.h>
#include <stdlib.h>

/* Max number of pipe-delimited tokens and per-token length. */
#ifndef PIPE_PARSE_MAX_TOKENS
#define PIPE_PARSE_MAX_TOKENS 64
#endif

/* Must be large enough to hold a full command fragment (see MAX_CMD_LEN in launcher_common.h). */
#ifndef PIPE_PARSE_MAX_TOKEN_LEN
#define PIPE_PARSE_MAX_TOKEN_LEN 4096
#endif

/**
 * Ordered pipe-delimited token list. Empty tokens are preserved so callers can
 * observe priority-of-empty semantics.
 *
 * fields:
 *   tokens[i]             - the i-th token (may be empty string "").
 *   count                 - number of tokens parsed.
 *   has_empty_priority    - 1 if the FIRST token is empty (leading '|'), i.e.
 *                           an explicit "no preference / empty value" takes
 *                           priority; 0 otherwise.
 */
typedef struct {
    char tokens[PIPE_PARSE_MAX_TOKENS][PIPE_PARSE_MAX_TOKEN_LEN];
    int count;
    int has_empty_priority;
} PipeTokenList;

/**
 * Parse a pipe-delimited string into an ordered token list, PRESERVING empty
 * tokens. The first token being empty marks empty-priority.
 *
 * Example:
 *   parse_pipe_tokens("tokenA|tokenB|tokenC", &out)
 *     -> out.tokens = {"tokenA","tokenB","tokenC"}, count=3, has_empty_priority=0
 *
 *   parse_pipe_tokens("|tokenA|tokenB|tokenC|", &out)
 *     -> out.tokens = {"","tokenA","tokenB","tokenC",""}, count=5, has_empty_priority=1
 *
 *   parse_pipe_tokens("", &out)
 *     -> count=0, has_empty_priority=1  (empty value => empty-priority)
 *
 * @param value  Null-terminated input string (may be NULL).
 * @param out    Pointer to a PipeTokenList that will be zero-initialized and filled.
 */
static inline void parse_pipe_tokens(const char* value, PipeTokenList* out) {
    if (!out) return;
    memset(out, 0, sizeof(*out));
    if (!value) return;

    size_t len = strlen(value);
    if (len == 0) {
        /* Empty value: empty-priority with no tokens. */
        out->has_empty_priority = 1;
        return;
    }

    const char* p = value;
    int idx = 0;
    while (idx < PIPE_PARSE_MAX_TOKENS) {
        const char* sep = strchr(p, '|');
        size_t tok_len = (sep) ? (size_t)(sep - p) : strlen(p);

        if (tok_len >= PIPE_PARSE_MAX_TOKEN_LEN) tok_len = PIPE_PARSE_MAX_TOKEN_LEN - 1;
        memcpy(out->tokens[idx], p, tok_len);
        out->tokens[idx][tok_len] = '\0';
        idx++;

        if (!sep) break;      /* last token */
        p = sep + 1;
    }
    out->count = idx;

    /* Empty-priority when the FIRST token is empty (leading '|'). */
    out->has_empty_priority = (out->count > 0 && out->tokens[0][0] == '\0');
}

/**
 * Compute the resolved default/first-token value from a pipe-delimited string,
 * honoring empty-priority: if the string begins with '|' (or is empty), the
 * resolved default is the empty string, meaning "no option/argument".
 *
 * This mirrors how config.json values inherited by Game.ini default to the
 * first identified token when queried via the launcher.
 *
 * @param value    Pipe-delimited string (may be NULL).
 * @param buf      Destination buffer.
 * @param buf_size Size of destination buffer.
 * @return 1 if a non-empty resolved token was written, 0 if resolved to empty.
 */
static inline int pipe_first_effective_token(const char* value,
                                             char* buf, size_t buf_size) {
    if (!buf || buf_size == 0) return 0;
    buf[0] = '\0';
    if (!value || *value == '\0') return 0;

    /* Leading '|' means empty-priority -> resolved value is empty. */
    if (*value == '|') return 0;

    const char* sep = strchr(value, '|');
    size_t tok_len = (sep) ? (size_t)(sep - value) : strlen(value);

    /* Trim trailing whitespace of the first token. */
    while (tok_len > 0 &&
           (value[tok_len - 1] == ' ' || value[tok_len - 1] == '\t')) {
        tok_len--;
    }
    /* Trim leading whitespace. */
    size_t start = 0;
    while (start < tok_len &&
           (value[start] == ' ' || value[start] == '\t')) {
        start++;
    }
    tok_len -= start;

    if (tok_len >= buf_size) tok_len = buf_size - 1;
    memcpy(buf, value + start, tok_len);
    buf[tok_len] = '\0';

    return (buf[0] != '\0');
}

#endif /* PIPE_PARSE_H */

