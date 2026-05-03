<script setup lang="ts">
/**
 * Admin layout shell. Renders the AdminSidebar on the left, an
 * <RouterView /> in the middle for the active sub-page, and the
 * shared 2FA action modal at the document root.
 *
 * Sub-pages live in pages/admin/* — Overview, Users, Coupons, Audit,
 * System, Settings. Each page handles its own data loaders + uses
 * the useAdminActions composable to open admin write actions through
 * the shared modal here.
 *
 * Server-side require_admin is the actual security boundary; the
 * router.beforeEach guard + the TopBar nav-link gate are UX layers
 * to avoid a "loading then 403" flash for non-admins.
 */
import AdminSidebar from "@/components/admin/AdminSidebar.vue";
import AdminActionModal from "@/components/admin/AdminActionModal.vue";
</script>

<template>
  <div class="flex h-[calc(100vh-44px)]">
    <AdminSidebar />
    <main class="flex-1 min-w-0 overflow-y-auto">
      <RouterView />
    </main>
    <!-- Module-state-driven modal. Always rendered; visible only when
         a page calls useAdminActions().open(...). Sits at the layout
         root so it's available regardless of which sub-page triggers it. -->
    <AdminActionModal />
  </div>
</template>
