# **PT-013 Probe 2**

## **Export-mimic: backtick per line, two trailing spaces**

`def hello():`  
`return "world"`  
`print(hello())`

## **Indent inside the backticks**

`def hello():`  
    `return "world"`  
`print(hello())`

## **Non-breaking spaces inside backticks**

`def hello():`  
    `return "world"`

## **Escaped fence as marker**

\`\`\`python def hello(): return "world" \`\`\`

## **Word marker**

CODE-BEGIN python def hello(): return "world" CODE-END

## **Blank line inside backtick-per-line**

`line one`  
   
`line three`

## **Backtick per line, no trailing spaces**

`alpha` `beta`