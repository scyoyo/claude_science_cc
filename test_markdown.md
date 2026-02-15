# Markdown Feature Test

## Basic Text Formatting

This is a **bold text** and this is *italic text*. You can also use ~~strikethrough~~.

## Lists

### Unordered List
- Item 1
- Item 2
  - Nested item 2.1
  - Nested item 2.2
- Item 3

### Ordered List
1. First item
2. Second item
3. Third item

### Task List (GFM)
- [x] Completed task
- [ ] Pending task
- [ ] Another task

## Links and Code

Visit [Google](https://www.google.com) or use inline code like `const x = 10;`.

## Code Blocks

```javascript
function fibonacci(n) {
  if (n <= 1) return n;
  return fibonacci(n - 1) + fibonacci(n - 2);
}
```

```python
def hello_world():
    print("Hello, World!")
    return 42
```

## Tables (GFM)

| Feature | Status | Priority |
|---------|--------|----------|
| Tables | ✅ Done | High |
| Math | ✅ Done | High |
| Images | ✅ Done | Medium |

## Math Formulas (LaTeX)

Inline math: $E = mc^2$

Block math:

$$
\int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}
$$

$$
\frac{d}{dx}\left( \int_{0}^{x} f(u)\,du\right)=f(x)
$$

## Blockquote

> This is a blockquote.
> It can span multiple lines.
>
> And multiple paragraphs.

## Horizontal Rule

---

## Headings

# H1 Heading
## H2 Heading
### H3 Heading
#### H4 Heading
##### H5 Heading
###### H6 Heading

## Long URL Test

This is a very long URL that should wrap properly: https://www.example.com/very/long/path/that/might/cause/overflow/issues/on/mobile/devices/123456789

## Long Code Test

```
this_is_a_very_long_line_of_code_that_should_trigger_horizontal_scrolling_instead_of_wrapping_to_prevent_breaking_code_formatting_1234567890
```
