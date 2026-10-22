# Code blocks

Inline `code` with ``a `b` c``, `a*b*c`, `<tag>`, `**not bold**`, **bold `code`**, *italic `code`*, escaped \` alone.

| Cell | Code |
| --- | --- |
| a | `code in cell` |
| `code first` | b |

- [ ] T-001 task with `code`
- [x] T-002 `code` first

## Fenced, with language and indentation

```python
def hello():
    return "world"

print(hello())
```

## Fenced, no language, markdown-looking lines

```
# not a heading
- not a bullet
> not a quote
1. not a list
**not bold** <b>tag</b> a & b < c
x = `a`
	tabbed
```

Prose after.
