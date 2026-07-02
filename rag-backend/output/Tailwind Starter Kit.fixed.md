<!-- page 1 -->

Tailwind CSS
Starter Kit
Created by
Visit for more
JS Mastery

jsmastery.pro

<!-- page 2 -->

Introduction
https://jsmastery.pro JavaScript Mastery
Hey there, fellow developer! Are you tired of the never￾ending cycle of tweaking and fine-tuning your CSS styles?
Do you find yourself wrestling with complex class names
and struggling to maintain a consistent design across your
projects? If you agree, then you're in for a treat!
Welcome to the world of Tailwind CSS – the game￾changer that's about to revolutionize the way you
approach web styling.
Are you ready to bid farewell to CSS stress and embrace a
new era of web design simplicity? The Tailwind Starter Kit
eBook is your gateway to efficient styling and captivating
designs. Join us as we venture into the world of Tailwind
CSS, demystifying its power and unleashing its potential.
So, whether you're sipping your morning coffee or burning
the midnight oil, dive into this eBook and emerge as a
Tailwind CSS virtuoso. The journey starts now – let's create
stunning, responsive, & impressive web designs together!

<!-- page 3 -->

CSS   Selector ::before, ::after
https://jsmastery.pro JavaScript Mastery
The ::before and ::after pseudo-selectors in CSS are used to
add content before or after an element without changing
the actual HTML structure.
They're great for inserting things like icons, decorative
elements, or even text.
These pseudo-elements are like invisible children of the
selected element—they only exist in CSS.
How Do They Work?
These pseudo-elements are like invisible children of the
selected element—they only exist in CSS.
Both ::before and ::after need the content property to
work. Even if you just want to insert an empty block or
shape, you still need to define content, even if it’s just an
empty string ("").
Here's how they behave:

<!-- page 4 -->

CSS   Selector ::before, ::after
https://jsmastery.pro JavaScript Mastery
::before
Creates content that shows before the main content of an
element.
::after
Creates content that shows after the main content of an
element.
Key Details and Example
Let’s break it down with a more detailed example.
Imagine you have a <button> that you want to style by
adding a decorative arrow before the text:
<button> </button> Click Me
Using ::before, you can insert an arrow before the "Click
Me" text like this:

<!-- page 5 -->

CSS   Selector ::before, ::after
https://jsmastery.pro JavaScript Mastery
button::before {

: " ";
: ;
: ;
: ;
}
content
color
font-size
margin-right
← /* Adds an arrow before the button text */

/* Colors the arrow blue */

/* Makes the arrow bigger */

/* Adds some space between the arrow
and the text */

blue
25px
8px
This CSS will add a blue left arrow in front of the "Click Me"
text, without touching the HTML.
The content Property
² Text or Symbols: You can insert text, symbols, or
characters with content. For example, content: "★";
adds a star symbol.
² Empty Content: If you just want to style something (like
a background or border) without adding any text, use
content: ""; (empty string).
² Images: You can also insert images using  
content: url('image.png');.

<!-- page 6 -->

CSS   Selector ::before, ::after
https://jsmastery.pro JavaScript Mastery
More Complex Example (with ::after)
Let’s say you want to add an icon after every link to make it
clear that it leads to an external site:
Imagine you have a <button> that you want to style by
adding a decorative arrow before the text:
<a > </a> href=" " Visit Example https://example.com
With ::after, you can add a small icon after the link:
a::after {

: " ";
: ;
}
content
margin-right
/* Adds a link icon after the text */

/* Adds a little space between the text
and icon */

5px
Now, the link would look like this: "Visit Example ".

<!-- page 7 -->

CSS   Selector ::before, ::after
https://jsmastery.pro JavaScript Mastery
Block or Inline?
By default, the ::before and ::after pseudo-elements
are inline. That means they behave like text—sitting on the
same line as the content.
But you can change this using display.
p Block Elements: If you want these pseudo-elements to
act like block elements (taking up the full width), you
can use display: block.
div::after {

: " ";

: ;

: ;

}
content
display
font-weight
Before the content
block
bold
This adds the text "Before the content" as a bold, block￾level element before a <div>'s content.

<!-- page 8 -->

CSS   Selector ::before, ::after
https://jsmastery.pro JavaScript Mastery
Styling Beyond Text
::before and ::after aren't just for adding text. You can
style them just like any other element. For example, you
can give them:
But you can change this using display.
 Background: Add a background color or even a
background image.
 Borders: Add borders to create decorative lines or
boxes.
 Positioning: Use position: absolute to position the
pseudo-elements relative to their parent.
Example: Adding a Decorative Shape
Suppose you want to add a decorative circle before a
heading. Here's how you could do it:
<h2> </h2> My Awesome Heading

<!-- page 9 -->

CSS   Selector ::before, ::after
https://jsmastery.pro JavaScript Mastery
And the CSS:
h2::before {

: "";
: ;
: ;

: ;

: ;
: ;
: ;
}
content
display
width
height
background-color
border-radius
margin-right
/* Empty content, we’re just adding a shape */

/* So it sits inline with the text

/* Makes the circle red */

/* Turns it into a circle */

/* Adds space between the circle and
the text */

inline-block
red
10px
10px
50%
10px
This will create a small red circle that appears before the
heading text, without touching the HTML.

<!-- page 10 -->

CSS   Selector ::before, ::after
https://jsmastery.pro JavaScript Mastery
Practical Uses
Here are some real-world uses for ::before and ::after:
[ Icons: Add icons before or after text (like arrows,
checkmarks, or symbols).
[ Quotes: Automatically add quote marks around
blockquotes without needing to write them in the HTML
[ Clearfix: A popular technique to clear floats in layouts
by adding an empty ::after element with  
clear: both (it’s called a clearfix hack).
[ Buttons or Links: Add visual cues like arrows, icons, or
decorative elements to make buttons and links more
engaging
[ Custom Shapes: Add custom shapes like dots, lines, or
borders for styling purposes.

<!-- page 11 -->

CSS   Selector ::before, ::after
https://jsmastery.pro JavaScript Mastery
Recap
Here are some real-world uses for ::before and ::after:
V ::before: Inserts content before an element's actual
content.
V ::after: Inserts content after an element's actual
content.
 They only work when you define the content property,
even if it’s just an empty string.
 You can style them with any CSS properties (color, size,
background, positioning, etc.).
 They're useful for adding decoration, symbols, icons, or
additional text without touching the HTML structure.
I hope this gives you a solid understanding of how
::before and ::after work!

<!-- page 12 -->

Tailwind CSS and Before after
https://jsmastery.pro JavaScript Mastery
Style the ::before and ::after pseudo-elements using
the before and after modifiers:
< ="
"> </ >
span
div
class after:content-['*'] after:ml-0.5
after:text-red-500 block... Email
When using these modifiers, Tailwind will automatically
add  by default so you don’t have to specify it
unless you want a different value.
content: ''

<!-- page 13 -->

Responsive design
https://jsmastery.pro JavaScript Mastery
Responsive design is a crucial aspect of modern web
development that ensures your website looks and
functions seamlessly across a variety of screen sizes and
devices. With Tailwind CSS, achieving responsive design is
made incredibly easy.
Tailwind CSS provides a range of utility classes that can be
applied conditionally based on different screen
breakpoints. These breakpoints are essentially specific
minimum widths that correspond to different device sizes.
Here are the default breakpoints along with their
associated prefix and CSS media query:
sm : 640px (min-width: 640px)
md : 768px (min-width: 768px)
lg : 1024px (min-width: 1024px)
xl : 1280px (min-width: 1280px)
2xl : 1536px (min-width: 1536px)

<!-- page 14 -->

Responsive design
https://jsmastery.pro JavaScript Mastery
To create responsive elements using Tailwind, you simply
prefix the utility class with the breakpoint name followed by
a colon. This indicates that the utility class should apply
only at or above that specific breakpoint.
It's important to note that Tailwind follows a mobile-first
approach. This means that unprefixed utilities, such as
those that control basic styles like text alignment and color,
apply to all screen sizes by default.
Prefixed utilities, like , only take effect at the
specified breakpoint and larger.
md:uppercase
To illustrate this concept, let's consider creating a
responsive card element using Tailwind:
:

<!-- page 15 -->

Responsive design
https://jsmastery.pro JavaScript Mastery
:
< ="
">

< =" ">

< =" ">

< ="
" =" " ="
" />

</ >

< =" ">

< =" " ="
"> </ >

< =" ">
</ >

</ >

</ >

</ >
div
div
div
img
div
div
a
a
p
p
div
div
div
class
class
class
class
src alt
class
href class
class
mx-auto max-w-md overflow-hidden rounded￾xl bg-gray-50 shadow-lg md:max-w-2xl
md:flex
md:shrink-0
h-52 w-full object-cover md:h￾full md:w-48 /img.jpg My image alt
description
p-8
# mt-1 block text-lg font￾bold leading-tight text-gray-800
mt-2 text-gray-500

My awesome card
Lorem ipsum
dolor sit amet, consectetur adipiscing elit. Donec
accumsan eros elementum massa dignissim.

<!-- page 16 -->

Responsive design
https://jsmastery.pro JavaScript Mastery
In this example, the class is applied to the outer
, making it a flex container on medium screens and
larger. The class ensures that the image
within the card does not shrink on medium and larger
screens. Various -prefixed utilities are used to control
the img dimensions & layout on medium & larger screens.
md:flex
<div>
md:shrink-0
md:
Remember, Tailwind CSS simplifies the process of creating
responsive designs by letting you easily manage styles for
different breakpoints. This way, your website remains
visually appealing and user-friendly across a wide range of
devices and screen sizes.
:

<!-- page 17 -->

Power of Tailwind CSS
https://jsmastery.pro JavaScript Mastery
In the ever-evolving landscape of frontend technologies,
one name is rising to the forefront: Tailwind CSS. This
framework has become synonymous with crafting
stunning web interfaces.
Whether you're diving into small demo projects or steering
enterprise-level ventures, the potency of Tailwind CSS
shines through – and this cheat sheet is your compass on
this exhilarating journey.
Tailwind CSS in a Nutshell:
Let's demystify the magic of Tailwind CSS. Imagine styling
your web pages without having to wrangle custom CSS
code. Tailwind's secret weapon lies in its utility-first
approach. It empowers you to effortlessly apply styles
using low-level utilities – the fundamental building blocks
of any web element. The best part?
You don't need to be a CSS guru. Understand the utility
classes and watch your designs come to life.

<!-- page 18 -->

From Vanilla CSS to Tailwind
https://jsmastery.pro JavaScript Mastery
Visualize a button element – a hallmark of web design.
Traditionally, crafting it with vanilla CSS requires a handful
of lines. Take a peek at the traditional approach:
Now, envision that button, transformed with the Tailwind
charm:
.button
inline-block

blue
white
none

pointer

{

: ;

: ;

: ;

: ;

: ;

: ;

: ;

: ;

}
display
padding
background-color
color
border
border-radius
cursor
font-size
10px 20px
0.25rem
16px
<button
>

</button>
=
Click Me

class "py-2 px-4 bg-blue-500 text-white rounded
cursor-pointer text-lg"

<!-- page 19 -->

Tailwind's Class Essentials
https://jsmastery.pro JavaScript Mastery
1. Categories
Remembering utility classes in Tailwind CSS can be made
simpler by grouping them into categories and
understanding the naming conventions. Here's a
straightforward way to remember and organize them:
Tailwind utility classes can be grouped into a few main
categories based on what they control:
Classes for controlling layout, such as margin, padding,
width, height, etc.
Classes for text-related styles like font size, font weight, text
alignment, etc.
Layout
Typography

<!-- page 20 -->

Tailwind's Class Essentials
https://jsmastery.pro JavaScript Mastery
Classes for handling background colors, text colors,
borders, etc.
Classes for building responsive layouts using Flexbox and
Grid.
Utility classes for managing spacing between elements
using margin and padding.
Classes for styling borders and controlling border radius.
Background & Color
Flexbox & Grid
Spacing
Borders

<!-- page 21 -->

Tailwind's Class Essentials
https://jsmastery.pro JavaScript Mastery
2. Naming Conventions
Tailwind uses a consistent naming convention for its utility
classes. Understanding the abbreviations and structure
can help you remember them:
Each utility class has a short abbreviation indicating what it
controls. For example, for margin, for padding, for
text-related properties, for background, etc.
m p text
bg
Tailwind classes often include modifiers that indicate the
level or specific value. For example, for small, for
large, for 2 extra large, for styles on hover, etc.
sm lg
2xl hover
After the abbreviation and modifier, the property name is
added. For example, for margin-2, for padding￾y-4, for center-aligned text, etc.
m-2 py-4
text-center
Abbreviations
Modifiers
Property

<!-- page 22 -->

Tailwind's Class Essentials
https://jsmastery.pro JavaScript Mastery
3. Examples
Here are a few examples to illustrate this approach:
m-4
Margin of 1rem (default spacing unit) on all sides.
py-8
Vertical padding of 2rem on top and bottom.
text-lg
Large font size for text.
bg-blue-500
Background color of a shade of blue.
flex flex-col
Apply Flexbox layout with column direction.
border border-gray-300
Gray border with a default width.

<!-- page 23 -->

Tailwind's Class Essentials
https://jsmastery.pro JavaScript Mastery
By understanding the categories, abbreviations, modifiers,
and property names, you can quickly recall and apply
Tailwind utility classes without needing to memorize every
single class.
It's all about breaking down the naming logic and knowing
where to find the classes you need for a specific styling
task.
One of the easiest ways to get started with Tailwind is by
using its interactive web browser mode on . Tailwind Play
This fantastic feature enables you to make updates to an
existing HTML page and instantly visualize the changes. It's
a perfect starting point, along with the comprehensive
, to explore various features and
get familiar with the Tailwind approach.
Tailwind documentation
With this interactive playground, you can quickly
experiment and see the power of Tailwind CSS in action!
Tailwind Play

<!-- page 24 -->

Dynamic States
https://jsmastery.pro JavaScript Mastery
You've Embraced Tailwind CSS – Now Embrace Its Dynamic
States!
Tailwind CSS is your go-to toolkit for crafting stylish and
responsive interfaces with ease. But in today's world, where
interactivity and adaptability reign supreme, static designs
just won't cut it. Modern applications call for dynamic
responses to user interactions and varying screen sizes.
Forget the headaches of traditional CSS frameworks!
Tailwind CSS empowers you to effortlessly implement
dynamic element states by harnessing the magic of CSS
pseudo-selectors as prefixes to its intuitive classes.
Need a captivating hover effect? Transform an element's
background on hover with a simple " " prefix: hover
< =" ">
</ >
div
div
class bg-gray-500 hover:bg-blue-600 ... Hover
Me

<!-- page 25 -->

Dynamic States
https://jsmastery.pro JavaScript Mastery
But wait, there's more! Tailwind CSS extends its prowess
beyond just "hover".
It embraces an array of pseudo-selectors that grant you
incredible versatility. For those complex scenarios, meet the
mighty "group" class. It empowers you to apply styles to
child elements based on the parent's state:
Elevate your design game with Tailwind CSS – Where
dynamic states are a breeze!
< =" ">

< =" ">
</ >

</ >
div
p
p
div
class
class
bg-blue-500 group ...
text-blue-300 group-hover:text-white
Click for more

<!-- page 26 -->

Dark Mode Enhancement
https://jsmastery.pro JavaScript Mastery
Tailwind CSS not only excels at responsive design but also
seamlessly integrates dark mode styling into your web
projects. With the dark mode variant, you can effortlessly
adapt your website's appearance when users switch to
dark mode.
Consider the same card example, now enhanced with dark
mode styling:
:

<!-- page 27 -->

Dark Mode Enhancement
https://jsmastery.pro JavaScript Mastery
Just like everything else, setting up and styling for dark and
light themes is easier than before.
To use dark mode, we need to make a small change. We
have to modify the configuration to include the dark class.
If we don't specify it, the theme styles will automatically
adapt based on the user's Operating System preference –
quite interesting!
We only need to mention this field if we want to offer a
theme toggle on the website. It's a choice we make! :
/** @type {import('tailwindcss').Config} **/

// ...

module.exports = {

: ' ',

: {

: {

},

},

: [],

}
darkMode
theme
extend
plugins
class

<!-- page 28 -->

Dark Mode Enhancement
https://jsmastery.pro JavaScript Mastery
:
< ="
">

< =" ">

< =" ">

< ="
" =" " ="
" />

</ >

< =" ">

< =" " ="
">
</ >

< ="
">
</ >

</ >

</ >

</ >

div
div
div
img
div
div
a
a
p
p
div
div
div
class
class
class
class
src alt
class
href class
class
mx-auto max-w-md overflow-hidden rounded￾xl bg-gray-50 shadow-lg dark:bg-slate-800 md:max￾w-2xl
md:flex
md:shrink-0
h-52 w-full object-cover md:h￾full md:w-48 /img.jpg My image alt
description
p-8
# mt-1 block text-lg font￾bold leading-tight text-gray-800 dark:text-white
mt-2 text-gray-500 dark:text￾gray-300

My
awesome card

Lorem ipsum dolor sit amet, consectetur
adipiscing elit. Donec accumsan eros elementum massa
dignissim.

In this updated example, the dark mode variant comes into
play. Let's break it down:

<!-- page 29 -->

Dark Mode Enhancement
https://jsmastery.pro JavaScript Mastery
< : This utility sets the background
color of the card to a darker shade (bg-slate-800)
when dark mode is enabled. This creates a visually
distinct experience for users who prefer dark themes.
dark:bg-slate-800
< : Here, the link text inside the card is
set to white (text-white) in dark mode. This ensures
good readability and maintains a consistent design
aesthetic.
dark:text-white
< : The paragraph text is given a
gray color (text-gray-300) to provide a suitable
contrast while maintaining the dark mode look.
dark:text-gray-300
Tailwind makes dark mode implementation hassle-free by
automatically detecting the user's preferred color scheme
through the prefers-color-scheme CSS media feature.
By incorporating these dark mode utilities, you enhance the
UX and demonstrate your attention to detail by providing a
design that adapts to different viewing preferences.
:

<!-- page 30 -->

Functions & Directives
https://jsmastery.pro JavaScript Mastery
Alright, gather 'round as we dive into the mesmerizing
world of Tailwind CSS – where functions and directives work
their enchantment on your styles.
Get ready for some behind-the-scenes wizardry that’ll
have your CSS dancing to your tune!
Directives: The Ringleaders of Style
Tailwind Directives: A Symphony of Style:
Let's talk directives – these are Tailwind's special
commands that make your CSS do a little jig.
:
This big boss directs the orchestra. It brings in Tailwind's
base, components, utilities, and variants styles into your
CSS. It's like your backstage pass to the styling show.
@tailwind:

<!-- page 31 -->

Functions & Directives
https://jsmastery.pro JavaScript Mastery
:
/* Injects base styles and plugin base styles */

/* Injects component classes and plugin component styles */

/* Injects utility classes and plugin utility styles */

/* Controls where variants are injected */

@tailwind ;
@tailwind ;

@tailwind ;
@tailwind
base
components
utilities
variants;
@layer {

}

@layer {

}

@layer {

}

base
components
utilities
/* Your base styles here */

/* Your component styles here */

/* Your utility styles here */

Meet the director of categories – base, components, and
utilities. You get to tell your styles which bucket to hop into.
@layer:

<!-- page 32 -->

Functions & Directives
https://jsmastery.pro JavaScript Mastery
:
@config " ";

@tailwind ;

@tailwind ;

@tailwind ;

./tailwind.admin.config.js
base
components
utilities
This one’s a ninja. It lets you sneak in existing utility classes
into your custom CSS. Think of it like mixing and matching
style ingredients.
Need a CSS file to follow different rules? Wave the @config
wand and let Tailwind know which config file to dance with.
@apply:
@config:
. {

;

}
custom-button
@apply bg-blue-500 text-white font-bold py-2 px-4 rounded

<!-- page 33 -->

Functions & Directives
https://jsmastery.pro JavaScript Mastery
Now, let’s talk functions. These are like spells that give you
dynamic powers over your styles.
Functions: CSS Sorcery Unleashed
:
This wizard lets you access Tailwind config values using dot
notation. It’s like whispering secrets to your styles.
Got a value with a dot? No problem – use square brackets.
theme()
. {
( - ( ));

}

content-area

: calc theme spacing height 100vh .12
.content-area

calc theme spacing[
{
: ( - ( ]));

}
height 100vh 2.5

<!-- page 34 -->

Functions & Directives
https://jsmastery.pro JavaScript Mastery
With screen(), you compose media queries that rock to the
rhythm of your breakpoints.
So, there you have it – functions and directives, the secret
ingredients that make Tailwind CSS so much more than
just styling.
:
Now, meet the maestro of media queries. It crafts these
responsive symphonies that perfectly match your
breakpoints.
screen()
@media sm

screen( ) {

}

/* Media query for the 'sm' breakpoint */

<!-- page 35 -->

Flexibility and Extendibility
https://jsmastery.pro JavaScript Mastery
The part lets you supercharge Tailwind CSS by
adding your own stuff, like new colors or spacing. When you
do this, Tailwind CSS automatically creates classes that
work seamlessly with the ones it already has.
theme
Want a taste of how this works? Check out this snippet
from your tailwind.config.js file. Here, we're switching up the
default sans fontFamily and throwing in a new color we're
calling nightown.
:
In the , you'll discover the cool
and fields. These are your tickets to unlocking
Tailwind CSS's awesomeness, letting you tweak it just the
way you want.
tailwind.config.js file theme
plugin
You can even change the values it comes with to make
Tailwind totally your own.
Theme

<!-- page 36 -->

Flexibility and Extendibility
https://jsmastery.pro JavaScript Mastery
:
Plugins are like the cherry on top that makes Tailwind even
more awesome. Let's highlight two standout plugins:
typography and forms.
Typography gives you classes to make your content look
all fancy with Markdown text—super useful when you're
working with HTML generated by CMS.
And Now, Plugins!
module =
theme {

fontFamily: {

sans: [ ]
,

extend:
colors {

nightown:
,

},

},

};
. {

:
' ', ' ', ' ' ,

}
{

:
' ',

}
exports
YourCustomFont system-ui sans-serif
#123456

<!-- page 37 -->

Flexibility and Extendibility
https://jsmastery.pro JavaScript Mastery
If you want to take control, you can slap on the form-input
classes to choose where these styles do their thing.
:
Forms are where it's at for styling your form elements like
input, textarea, and select. They come pre-styled so your
forms look slick right out of the box.
With Tailwind CSS, you're in for a ride of endless
customization and style expansion. It's all about making
your styles your own, and Tailwind's got your back.

<!-- page 38 -->

Accessibility in Tailwind
https://jsmastery.pro JavaScript Mastery
:
Tailwind has your back when it comes to accessibility,
especially for screen readers. It provides nifty utilities like
sr-only and not-sr-only classes to ensure a seamless
experience for all users.
Imagine an <a> tag with an SVG icon and a hidden text for
screen readers.
The sr-only class does the magic – it makes the "User
Profile" text invisible to the naked eye but still there for those
who rely on screen readers.
The Invisible Hero: Class sr-only
< >

< > </ >

< </ >

</ >
a
svg svg
span > span
a
=

= User Profile
href
class
"#"
"sr-only"
<!-- ... -->

<!-- page 39 -->

Accessibility in Tailwind
https://jsmastery.pro JavaScript Mastery
:
Now, let’s say you want to show the text for larger screens
but keep it hidden for smaller ones. The sm:not-sr-only
class combo is your ticket to this flex.
With this, the text remains hidden for small screens, but
magically appears on larger ones.
Tailwind’s accessibility utilities are like bridges that connect
all users to your content.
With sr-only and not-sr-only, you’re weaving a tapestry
of inclusivity where everyone gets a front-row seat, no
matter how they experience your site.
Hiding on Demand: Class not-sr-only
Creating Bridges to Inclusion:
< =" ">

< > </ >

< =" "> </ >

</ >

a
svg svg
span span
a
href
class
#
sr-only sm:not-sr-only
<!-- ... -->
User Profile

<!-- page 40 -->

Animations and Interactivity
https://jsmastery.pro JavaScript Mastery
:
Let's venture into the world of animations and interactivity,
where Tailwind CSS truly shines. Get ready to add dynamic
flair to your designs!
Start with smooth transitions using the transition-
{properties} utilities. These help you specify which
properties should transition when they change. For eg:
Tailwind offers four standard animations to give life to your
elements:
Transitions
Animations
< ="
">

</ >
button
button
class transition ease-in-out delay-150 bg-blue-500
hover:-translate-y-1 hover:scale-110 hover:bg-indigo-500
duration-300 ...
Download

<!-- page 41 -->

Animations and Interactivity
https://jsmastery.pro JavaScript Mastery
:
Create a spinning animation, like a loading indicator, with
the animate-spin utility. Example:
Make an element scale and fade like a radar ping
animation using animate-ping. Example:
Add a gentle fade-in and fade-out animation to an
element with animate-pulse. Example:
Spin Animation
Ping Animation
Pulse Animation
< =" "></ > div div class animate-spin h-6 w-6 ...
< =" "></ > div div class animate-spin h-6 w-6 ...
< =" "></ > div div class animate-pulse h-8 w-8 rounded-full ...

<!-- page 42 -->

Animations and Interactivity
https://jsmastery.pro JavaScript Mastery
:
Use animate-bounce to make an element bounce up and
down. Example:
Control cursor appearance on hover:
Bounce Animation
Cursor Styles
Tailwind makes your elements interactive and engaging:
Interactivity
< =" "></ > div div class animate-bounce h-10 w-10 rounded ...
< =" "> </ >

< =" "> </ >

< =" "> </ >
button button
button button
button button
class
class
class
cursor-pointer ...
cursor-wait ...
cursor-not-allowed ...
Click me
Please wait
No access

<!-- page 43 -->

Animations and Interactivity
https://jsmastery.pro JavaScript Mastery
:
Enable or disable pointer interactions:
Pointer Events
With these animations and interactive elements, Tailwind
CSS lets you create engaging and user-friendly designs
effortlessly. It's all about adding that extra layer of magic to
your web projects!
< =" "> </ >

< =" "> </ >
div div
div div
class
class
pointer-events-auto ...
pointer-events-none ...
Clickable
Not clickable

<!-- page 44 -->

Tips & Tricks
https://jsmastery.pro JavaScript Mastery
Now that you have understood, what tailwindcss is and
how it works, let’s explore a few tips & tricks.
We’ll first explore the tricks or special utilities we can use to
make our development more efficient:
Changes the default browser color for elements like
checkboxes and radio groups
Accent
< =" ">

< > < =" " />
</ >

< > < =" " =" "
/> </ >

</ >
div
label input
label
label input
label
div
class
type checked
type class
checked
my-4 flex flex-col
checkbox
checkbox accent-pink-500
Browser default

Customized
Browser default
Customized

<!-- page 45 -->

Tips & Tricks
https://jsmastery.pro JavaScript Mastery
Usually, when building a responsive website, we have to
take care of the text size on different devices.

Something like this:
Using the custom style approach we discussed and the
min CSS function, we can do something like this:
The result, the second approach is much better and more
responsive than the other. Instead of relying on the media
screen, we kind of calculate the value depending on the
screen size automatically.
Something Nice
Something Fluid Something Fluid
Something Nice
Fluid Texts
< =" "> </ > p p class sm:text-7xl text-5xl Something Nice
< =" "> </ > p p class text-[min(10vw,70px)] Something Fluid

<!-- page 46 -->

Tips & Tricks
https://jsmastery.pro JavaScript Mastery
Well, yeah. If you take the time to learn it well, you can
perform certain tasks that are typically done using
JavaScript with tailwindcss alone, without requiring
JavaScript. It might sound incredible, right?
Think about how often we've made an accordion or relied
on libraries or states to manage it.
Let me demonstrate an example of how we can achieve
this without using JavaScript, just with pure tailwindcss.
Less JavaScript
< =" ">

< ="
" >

< ="
">

</ >

< ="
">

< >
</ >

</ >

</ >

</ >
div
details
summary
summary
div
p
p
div
details
div
class
class
open
class
class
max-w-lg mx-auto p-8
open:bg-white dark:open:bg-slate-900 open:ring-1
open:ring-black/5 dark:open:ring-white/10 open:shadow-lg p-6
rounded-lg
text-sm leading-6 text-slate-900 dark:text-white
font-semibold select-none
mt-3 text-sm leading-6 text-slate-600 dark:text￾slate-400

Why do they call it Ovaltine?

The mug is round. The jar is round. They should call it
Roundtine.

<!-- page 47 -->

Tips & Tricks
https://jsmastery.pro JavaScript Mastery
Isn’t that crazy???
We used the open: selector along with proper HTML tags,
i.e., details (without which we won’t get that toggle).
Why do they call it Ovaltine?
Why do they call it Ovaltine?
The mug is round. The jar is round. They should call it Roundtine.
If you worked with file inputs, you know the pain of styling
the default layout.
Thankfully, Tailwindcss provides a better solution
File
Use the prefix and use any utility to customize the
input however you want
file:

<!-- page 48 -->

Tips & Tricks
https://jsmastery.pro JavaScript Mastery
< =" ">

< =" " ="
" />

</ >
label
input
label
class
type class
my-4 block
file block w-full text-sm text-slate-500
file:mr-4 file:rounded-full file:border-0 file:bg-violet-50
file:px-4 file:py-2 file:text-sm file:font-semibold file:text￾violet-700 hover:file:bg-violet-100
Do you want to override the default blue or other highlight
that appears when a user selects a text on your website?
Tailwindcss’s selection is a way to go
Be creative, do whatever you want. You have to complete
control by using just a few lines of code
Subscribe to JavaScript Mastery YT channel
Highlight
< =" ">

< > </ >

</ >
div
p p
div
class selection:bg-green-400 selection:text-white
Subscribe to JavaScript Mastery YT channel

<!-- page 49 -->

Tips & Tricks
https://jsmastery.pro JavaScript Mastery
Not a fan of white or black caret? Use tailwindcss then
Try typing it into textarea, and you’ll notice the caret color
to be pink
Caret
Many More
These are just a handful of examples. Tailwindcss offers
many unique tools such as those for different states like
before: & active:, styles that work only on certain screen
sizes like landscape or portrait, styles for ARIA and screen
readers, gradients animations, and it even lets you apply
distinct styles when printing.
< ="
" =" "></ >
textarea
textarea
class
placeholder
w-full border border-zinc-200 caret￾pink-500 p-2 type something..
Type something..

<!-- page 50 -->

Tailwind Component Libraries
https://jsmastery.pro JavaScript Mastery
A premium collection of meticulously crafted user
interface components and templates built using the
Tailwind CSS framework.
Visit
A set of unstyled, fully accessible UI components that
can be used as a foundation for creating custom
designs. Built by the creators of Tailwind CSS.
Visit
Shadcn
Shadcn combines the power of Tailwind with artistic
designs. Beautifully designed components built with
Radix UI and Tailwind CSS.
Visit

<!-- page 51 -->

Tailwind Component Libraries
https://jsmastery.pro JavaScript Mastery
Tail-kit provides a comprehensive set of carefully
crafted, easy to customize, fully responsive UI
components, Templates & Tools for your Tailwind CSS.
Tailkit Visit
Radix UI is a cutting-edge toolkit designed to create
advanced UI components with an emphasis on
accessibility and user experience.
Visit
Preline UI is an open-source set of prebuilt UI
components based on the utility-first Tailwind CSS
framework. With a focus on high-quality design.
Visit

<!-- page 52 -->

Tailwind Component Libraries
https://jsmastery.pro JavaScript Mastery
The most popular component library for Tailwind CSS.

daisyUI adds component class names to Tailwind CSS
so you can make beautiful websites faster than ever.
Visit
Hyper
Explore an extensive array of ready-to-use
components, organized into three distinct categories:
marketing, e-commerce, and applications.
Visit
Contemporary Tailwind CSS component library with
150+ rich components for app & product development.
Each offers multiple variations to suit your requirement
Visit

<!-- page 53 -->

Tailwind Component Libraries
https://jsmastery.pro JavaScript Mastery
Tailwind Elements
With more than 500 tailwind components. These
components are based on the Bootstrap framework,
but they have a better design & a lot more functional.
Visit
This is a library that contains a wide variety of free
and paid templates. They have a collection of around
25 templates, mostly geared toward startup & saas.
Visit
Tailblocks
A collection of predefined Tailwind CSS components
designed to facilitate rapid website prototyping and
development.
Visit

<!-- page 54 -->

Tailwind Component Libraries
https://jsmastery.pro JavaScript Mastery
It offers a wide selection of 150+ Tailwind components
and templates with versatile styles. It's adaptable for
various frameworks like Angular, Vue, React, Svelte, etc.
Visit
Sira
Sira a design system with reusable components.
Compatible with Vue, React, and more. Offers
themes, dark mode, & predefined Tailwind styles.
Visit
Containing over 500 complimentary and premium
components, blocks, sections, and templates, this kit
offers an extensive selection.
Visit

<!-- page 55 -->

The End
https://jsmastery.pro JavaScript Mastery
Congratulations on reaching the end of our guide! But
hey, learning doesn't have to stop here.
If you're eager to dive deep into something this specific
and build substantial projects, our
has got you covered.
special course on
Next.js
The Ultimate

Next 14 Course
If you're craving a more personalized learning
experience with the guidance of expert mentors, we
have something for you — . Dev Career Accelerator
Dev Career Accelerator
If this sounds like something you need, then don’t stop
yourself from leveling up your skills from junior to senior.
Keep the learning momentum going. Cheers!