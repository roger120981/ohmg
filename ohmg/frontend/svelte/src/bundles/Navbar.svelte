<script>
import IconContext from 'phosphor-svelte/lib/IconContext';
import CaretDown from "phosphor-svelte/lib/CaretDown";
import { iconProps } from "@lib/utils"

import OpenModalButton from '@components/base/OpenModalButton.svelte';
import NavDropdown from '@components/layout/NavDropdown.svelte';
import SigninModal from '@components/layout/SigninModal.svelte';
import Link from '@components/base/Link.svelte';

export let CONTEXT;

let subMenus = {
	"georef": {
		"visible": false,
		"links": [
			{
				"title": "Find an item...",
				"href": "/browse#items",
				"external": false,
			},
			{
				"title": "All contributors",
				"href": "/profiles",
				"external": false,
			},
			{
				"title": "All activity",
				"href": "/activity",
				"external": false,
			},
			{
				"title": "Full documentation",
				"href": "https://ohmg.dev/docs",
				"external": true,
			},
		]
	},
	"about": {
		"visible": false,
		"links": [
			{
				"title": "News",
				"href": "/news",
				"external": false,
			},
			{
				"title": "FAQ",
				"href": "/faq",
				"external": false,
			},
			{
				"title": "Contact",
				"href": "/contact",
				"external": false,
			},
			{
				"title": "About Sanborn maps",
				"href": "/about-sanborn-maps",
				"external": false,
			},
			{
				"title": "About this site...",
				"href": "/about",
				"external": false,
			},
		]
	},
	"user": {
		"visible": false,
		"links": [
			{
				"title": CONTEXT.user.username,
				"href": "",
				"external": false,
			},
			{
				"title": "My Profile",
				"href": CONTEXT.user.profile_url,
				"external": false,
			},
			{
				"title": "Sign Out",
				"href": "/account/logout",
				"external": false,
			},
		]
	}
}

function clickOutside(node, { enabled: initialEnabled, cb }) {
    const handleOutsideClick = ({ target }) => {
      if (!node.contains(target)) {
        cb();
      }
    };

    function update({enabled}) {
      if (enabled) {
        window.addEventListener('click', handleOutsideClick);
      } else {
        window.removeEventListener('click', handleOutsideClick);
      }
    }

    update({ enabled: initialEnabled });
    return {
      update,
      destroy() {
        window.removeEventListener( 'click', handleOutsideClick );
      }
    };
  }
</script>

<IconContext values={iconProps}>
<SigninModal csrfToken={CONTEXT.csrf_token} />
<nav>
	<div>
		<div>
			<Link href="/" title="Home">
				<img style="height:30px; width:30px;" src="/static/img/colored-full-linework.png" alt="OldInsuranceMaps.net Home" class="navbar-brand-new">
			</Link>
		</div>
		<div style="padding-left: 8px;">
			<Link href="/browse" classes={["white"]}>Search</Link>
		</div>
		<div class="dropdown-container {subMenus.georef.visible ? 'active' : ''}" use:clickOutside={{ enabled: subMenus.georef.visible, cb: () => subMenus.georef.visible = false }} >
			<button on:click={() => {subMenus.georef.visible = !subMenus.georef.visible}} title="Georeferencing">Georeferencing <CaretDown /></button>
			{#if subMenus.georef.visible}
			<NavDropdown LINKS={subMenus.georef.links} />
			{/if}
		</div>
		<div class="dropdown-container {subMenus.about.visible ? 'active' : ''}" use:clickOutside={{ enabled: subMenus.about.visible, cb: () => subMenus.about.visible = false }} >
			<button on:click={() => {subMenus.about.visible = !subMenus.about.visible}} title="About">About <CaretDown /></button>
			{#if subMenus.about.visible}
			<NavDropdown LINKS={subMenus.about.links} />
			{/if}
		</div>
	</div>
	<div>
		{#if CONTEXT.user.is_authenticated }
		<div class="dropdown-container {subMenus.user.visible ? 'active' : ''}" use:clickOutside={{ enabled: subMenus.user.visible, cb: () => subMenus.user.visible = false }} >
			<button on:click={() => {subMenus.user.visible = !subMenus.user.visible}} title={CONTEXT.user.username}>
				<img style="height:45px; width:45px;" src={CONTEXT.user.image_url} class="navbar-brand-new" alt={CONTEXT.user.username} /><CaretDown />
			</button>
			{#if subMenus.user.visible}
			<NavDropdown LINKS={subMenus.user.links} RIGHT_POS={0}/>
			{/if}
		</div>
		{:else}
		<OpenModalButton modalId="signin-modal" style="nav-link" icon="none">Sign in</OpenModalButton>
		{/if}
	</div>
</nav>
</IconContext>
<style>
nav {
	display: flex;
	height: 40px;
	background:#123B4F;
	box-shadow: rgba(0, 0, 0, 0.1) 0px 1px 2px 0px;
    position: fixed;
    top: 0;
    right: 0;
    left: 0;
    z-index: 1030;
    display: flex;
    align-items: center;
    justify-content: space-between;
	padding: 0px 10px;
	color:white;
	font-weight: 500;
	overflow-x: auto;
	border: none;
	max-width: 100vw;
}

nav button {
	color: white;
	font-size: inherit;
}

nav button:hover {
	color: #cecece;
	cursor: pointer;
}

nav > div {
	display: flex;
	align-items: center;
}

nav > div > div {
	padding: 4px;
	white-space: nowrap;
}

.active button {
	color: #cecece !important;
}

.dropdown-container button {
	display: flex;
	flex-direction: row;
	align-items: center;
	background: none;
	border: none;
}

@media (max-width: 760px) {
	nav {
		padding: 0px 5px;
	}
}

</style>
