# MathMemo
Project Description

### Column Name
- - [ ] Task title ~3d #type @name yyyy-mm-dd  
-   - [ ] Sub-task or description  
 
- [ ] edit preivous "committed" messsages

### Brainstorm Ideas

- [*] scrolling IM style widget 
- [ ] block mode vs inline
- [ ] do we want to access the html? I'm not inclined to make this the default mode of operation.

- [ ] Optional vim bindings, maybe using fakevim
- [ ] LaTeX/Mathjax syntax highlighting
- [ ] Syntax completion
  - [ ] push one of the closing objets such as \right) ahead of the cursor.  we may not know the order, but when it gets typed, we can pull it out of the 'stack' ahead of the cursor. maybe offer it as a suggestion to complete as typing occurs in a pulldown thing
  - [ ] bad syntax delay/completeion record last good syntax and maybe don't process open {^_ until closed.  or maybe process it separately. maybe close it tenatively.  sth like a \dfrac could get two advanced {} ahead of it.  \dfrac... {} ...{}.  Hit tab/return to close it.
  - [ ] maybe add some kind of empty box after ^ and _ to indicate what is expected
- [ ] history
- [ ] save preferences/export colors/geometry
- [ ] toolbar for copy type shortcuts
- [ ] theming stuff / follow default theme / appropriate icon colors
- [ ] tabbed interface - multiple session 
- [ ] merge equations
- [ ] wizard for creating matrices or other elements
- [ ] collapse text elements between {}
- [ ] edit history
- [ ] autocompletion with candidate guessing
- [ ] macros / hot keys
- [ ] hide preview window when empty

- [ ] how do we tell if mathjax gave an error? .. one is yellow bg.
- 	2 is.. $$?  maybe no svg generated?


### clean this up:

- #### yellow syntax error
- 	unappended ^ or _
- 	no closing \right)
- 	#propose: adding a tenative {} to ^_
- 		# or tenative double {} to a frac/dfrac/tfrac

- ### $$ no process error:
- 	unmatched {  or nothing after \

- #if we're editing in the middle? where do the tentatiive items go?
- 	do we add the tentative closing } directly after? the cursor?
-         does it trail the cursor as we move?  should we maybe add
- 	a red mark in the eq to show the location of the cursor? of
- 	what would be typed if we type somethign?  like maybe a red |
- 	or box.. that's an interesting idea

- #what if you could highlight a potential block to surround with {}?
- 	and when you highlight in the editor, it would show highlights
- 	in the formula as well.


- # how about a tree structure that parses the things and shows where
- # we are in the tree..(or at least shows the cursor)

- # \left. and \right.  seem to show nothing.. could be useful
- # maybe show the phantom things as greyed out or some other color
- # to note that they don't exist yet.
- # and a red or gray cursor to show where the cursor is in the
- # image equation.  \color{red}xxx seems useful, or {\color{red} |}
- # is better

- #this post might be helpful for animated SVG in mathjax
- https://stackoverflow.com/questions/68469519/animating-mathjax-through-svg-animations

- #or this
- https://stackoverflow.com/questions/29205294/how-to-achieve-blinkin





- ### Completed Column ✓
- [x] can copy imge to clipboard and paste in an IM
- [x] draft mode with preview before commit
- [x] menubar, save dialogs, preferences
- [x] save a session
