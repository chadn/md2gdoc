# PT-013 Probe 1

## Inline

Text then `code` then text.
`start` at line start.
Backticks inside: ``a `b` c`` done.
Stars inside: `a*b*c` and `_x_` and `<tag>` and `**bold?**`.
Adjacent: **bold `code` bold** and *italic `code` italic*.
Two codes: `one` and `two`.
Escaped backtick \` alone.

| Cell | Code |
| --- | --- |
| a | `code in cell` |
| `code first` | b |

- [ ] T-001 task with `code` in it
- [x] T-002 `code` at start of task
- Bullet with `code`

## Fenced with language

```python
def hello():
    return "world"
```

## Fenced without language

```
# not a heading
- not a bullet
> not a quote
1. not a list
    indented four
	tabbed
**not bold** and *not italic* and `tick`
<b>not html</b>
a & b < c

after blank line inside block
```

## Tilde fence

~~~
tilde fenced
~~~

## Indented code

Paragraph before.

    indented line one
    indented line two

Paragraph after.

## Fenced in a list

- Item with code:

  ```sh
  echo hi
  ```

- Next item
