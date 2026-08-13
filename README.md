PHASE 1: Ecommerce website building with django restframework
- Started by creating Store app with all models needed for the ecommerce store.
- Models created are Product, order, customer, category.
- Created views for login, logout, register for new users.
- Created various demo bootstrap html templates to help with design of the django backend.
- Created Cart app enabled user to add product to cart, update cart product quantities, delete product from cart.
- Used ajax (AJAX allows a web page to communicate with a server in the background and update specific parts of the screen without reloading the entire page.) to help with communication with django in realtime.

PHASE 2: Working on user profile
- Added User details update page for user to update details
- Added a way for user to be able to change their password once it might be compromised
- Added extended user profile for user to add more details eith a model called Profile.
- we created an update info user info page bu encountered a bug because there is a problem when user doesn't have a profile. the system render through the profile query and returns an error which means that for the update_info page template to work the user should have a profile created in django admin page. 
- We added a search functionality that enables user to search by names or decription.