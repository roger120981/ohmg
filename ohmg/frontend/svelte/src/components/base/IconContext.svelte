<script>
    import { iconProps } from "@lib/utils"
    import IconContext from "phosphor-svelte/lib/IconContext";
    export let values = {}

    if (!values.weight) {
        values.weight = "bold"
    }
</script>

<IconContext values={values} />

