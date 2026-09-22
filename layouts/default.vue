<template>
  <div>
    <header>
      <NuxtLink to="/" class="brand">ВЫБОРЫ<span>.</span></NuxtLink>
      <p>Открытые результаты и проверяемые исходные данные</p>
    </header>
    <main><slot /></main>
    <footer>Vibori · статический проект · данные хранятся в открытом JSON</footer>
  </div>
</template>
