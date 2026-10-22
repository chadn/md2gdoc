# PT-013 Probe 4

## NBSP in prose

before after

## NBSP indent inside backticks

`def hello():`  
`    return "world"`  
`print(hello())`

## NBSP-only line

`line one`  
` `  
`line three`

## Backticks inside code lines

``x = `a` ``  
`z = 1`

## Tab inside backticks

`def hello():`  
`	return "world"`

## Trailing spaces inside code

`end   `  
`next`

## Markdown-sensitive starts inside backticks

`# comment`  
`- dash`  
`1. one`  
`> gt`  
`* star`  
`<b>tag</b>`

## Two blocks separated by prose

`block one`

Prose between.

`block two`
