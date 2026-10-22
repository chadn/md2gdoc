# PT-013 Probe 6

## Entity in prose

before&nbsp;after and before&#160;after

## Entity indent outside backticks

`def hello():`  
&nbsp;&nbsp;&nbsp;&nbsp;`return "world"`  
`print(hello())`

## Numeric entity indent outside backticks

`def hello():`  
&#160;&#160;&#160;&#160;`return "world"`  
`print(hello())`

## Entity inside backticks

`def hello():`  
`&nbsp;&nbsp;&nbsp;&nbsp;return "world"`  
`print(hello())`

## Entity-only line as blank

`line one`  
&nbsp;  
`line three`

## Entity inside backticks as blank

`line one`  
`&nbsp;`  
`line three`

## Code lines inside a list item

- Item with code:  
  `echo hi`  
  `echo there`
- Next item

## Code lines inside a task

- [ ] T-001 task:  
  `echo hi`
