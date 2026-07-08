package com.novig.replay;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Minimal reader for the flat (no nested arrays/objects) JSON-per-line rows this
 * pipeline's pollers write -- captured rows are always a dataclass's fields plus
 * "captured_at", never nested -- so a hand-rolled reader avoids pulling in a JSON
 * library for something this simple. Values come back as raw strings; callers
 * parse to long/boolean as needed. A JSON null comes back as a null map value.
 */
public final class NdjsonReader {

    private NdjsonReader() {}

    public static Map<String, String> parseRow(String line) {
        Map<String, String> result = new LinkedHashMap<>();
        int i = skipWhitespace(line, 0);
        if (i >= line.length() || line.charAt(i) != '{') {
            throw new IllegalArgumentException("expected '{' at start of row: " + line);
        }
        i = skipWhitespace(line, i + 1);
        if (i < line.length() && line.charAt(i) == '}') {
            return result;
        }

        while (true) {
            i = skipWhitespace(line, i);
            if (line.charAt(i) != '"') {
                throw new IllegalArgumentException("expected string key at position " + i + " in: " + line);
            }
            int[] cursor = new int[1];
            String key = parseString(line, i, cursor);
            i = skipWhitespace(line, cursor[0]);
            if (line.charAt(i) != ':') {
                throw new IllegalArgumentException("expected ':' after key '" + key + "' in: " + line);
            }
            i = skipWhitespace(line, i + 1);

            String value;
            if (line.charAt(i) == '"') {
                value = parseString(line, i, cursor);
                i = cursor[0];
            } else {
                int start = i;
                while (i < line.length() && line.charAt(i) != ',' && line.charAt(i) != '}') {
                    i++;
                }
                String literal = line.substring(start, i).trim();
                value = "null".equals(literal) ? null : literal;
            }
            result.put(key, value);

            i = skipWhitespace(line, i);
            if (i >= line.length()) {
                throw new IllegalArgumentException("unterminated JSON object: " + line);
            }
            char c = line.charAt(i);
            if (c == ',') {
                i++;
            } else if (c == '}') {
                break;
            } else {
                throw new IllegalArgumentException("expected ',' or '}' at position " + i + " in: " + line);
            }
        }
        return result;
    }

    private static int skipWhitespace(String s, int i) {
        while (i < s.length() && Character.isWhitespace(s.charAt(i))) {
            i++;
        }
        return i;
    }

    /** Parses the quoted string starting at s.charAt(start) == '"'; writes the index just past the closing quote to cursorOut[0]. */
    private static String parseString(String s, int start, int[] cursorOut) {
        StringBuilder sb = new StringBuilder();
        int i = start + 1;
        while (true) {
            if (i >= s.length()) {
                throw new IllegalArgumentException("unterminated string in: " + s);
            }
            char c = s.charAt(i);
            if (c == '"') {
                i++;
                break;
            }
            if (c == '\\') {
                char escaped = s.charAt(i + 1);
                switch (escaped) {
                    case '"': sb.append('"'); break;
                    case '\\': sb.append('\\'); break;
                    case '/': sb.append('/'); break;
                    case 'n': sb.append('\n'); break;
                    case 't': sb.append('\t'); break;
                    case 'r': sb.append('\r'); break;
                    case 'b': sb.append('\b'); break;
                    case 'f': sb.append('\f'); break;
                    case 'u':
                        String hex = s.substring(i + 2, i + 6);
                        sb.append((char) Integer.parseInt(hex, 16));
                        i += 4;
                        break;
                    default:
                        throw new IllegalArgumentException("unknown escape \\" + escaped + " in: " + s);
                }
                i += 2;
            } else {
                sb.append(c);
                i++;
            }
        }
        cursorOut[0] = i;
        return sb.toString();
    }
}
