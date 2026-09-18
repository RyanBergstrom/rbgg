This is the suplimental human provided information for the board game Lost Cities.

- Name: Lost Cities
- Link to the board game Geek listing https://boardgamegeek.com/boardgame/50/lost-cities
- Rules: C:\Dev\rbgg\documentation\lost-cities\lost_cities_rules.md

Images for the game is in this \imgs\ folder. They need to be copied to a game specific img folder for the game.

lost-cities-box-art.webp is the art for the game config page

CARDS
The game has 60 cards
5 Destinations/colors
blue: i,i,i,2,3,4,5,6,7,8,9,10
yellow: i,i,i,2,3,4,5,6,7,8,9,10
red: i,i,i,2,3,4,5,6,7,8,9,10
white: i,i,i,2,3,4,5,6,7,8,9,10
green: i,i,i,2,3,4,5,6,7,8,9,10

card_backs.jpg represents the card backs.

    naming convention for the card fronts:
        first letter of color_card #
        i=investment card
        base = the destination/base location for start of the discard piles

    example:
        blue 9 = b_9
        green 10 = g_10

the rbgg framework organizes the game into panels.

Progress(required) - show the navigation status
Gameboard(required) - display the card layout, and reserved positions for the cards to be stacked. Card bases spaced out 5 accross with the face down deck at the far right
Player 1 Hand - a panel to display the hand for the human players cards

Game notes - The cards are larger scale then the game needs, so they need to be scalable so that they fit on the screen and when the screen is resized they scale accordingly, not overflow.

I will be playing against an AI opponent, so no need for a 2nd players hand pannel

Partial suggested Suggested Yaml configurations

        difficulty:
        easy: 50
        medium: 300
        hard: 1500
        expert: 5000
        default: medium

        rounds:

        - name: Main Game
        turns:
        - name: Player Turn
            phases:
            - name: play_a_card
            text: "Play a Card to either an Expedition or to a discard pile"
            order: 1
            confirm:
            required: false
            - name: draw_a_card
            text: "Draw a new card but not one you Discarded"
            order: 1
            confirm:
                required: true
                name: "Confirm"
                description: "End your turn"
